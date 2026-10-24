"""Harmless draft-release canary. No sensitive producer is enabled by this tool.

Only the existing manually selected LAB workflow may invoke the three phases.
All HTTP is injected in tests; no retry, overwrite, delete or publish exists.
"""
import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import resource
import signal
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import build_opener, HTTPRedirectHandler, ProxyHandler, Request

REPOSITORY = "NickNicky19/NFL-forecasting"
API = "https://api.github.com"
CONTROL_REPO = "cli/cli"
CONTROL_TAG = "v2.0.0"
CONTROL_NAME = "gh_2.0.0_checksums.txt"
FIXTURE_NAME = "nfl-lab-private-storage-canary.txt"
EXISTING_CONFIG_RELATIVE = "config/private-storage-existing-canary-v1.json"
EXISTING_CONFIG_SHA256 = "7e320f66f8dda6ce91e5f95198bec203617457293ceeae950ee5f7bd52022ecc"
CDN_HOSTS = frozenset({"release-assets.githubusercontent.com", "objects.githubusercontent.com",
    "github-releases.githubusercontent.com"})
MAX_CALLS, MAX_TRANSFER, MAX_SUMMARY = 20, 1024 * 1024, 16 * 1024
MAX_RESPONSE, MAX_CONTROL_BODY = 128 * 1024, 16 * 1024
STATUSES = {"WRITE_CANARY_CREATED", "READ_BOUNDARY_DENIED", "RESTORE_EXACT_BODY_VERIFIED",
    "EXISTING_CANARY_PINNED",
    "FAIL_PRIVATE_BOUNDARY", "INCONCLUSIVE_DENIAL", "PUBLIC_CONTROL_FAILED",
    "DRAFT_IDENTITY_REQUIRED", "ASSET_IDENTITY_REQUIRED", "RESTORE_MISMATCH",
    "PROBE_GUARD_STOP", "PROBE_INTERNAL_ERROR"}


class ProbeError(Exception):
    def __init__(self, state="PROBE_GUARD_STOP"):
        self.state = state if state in STATUSES else "PROBE_GUARD_STOP"
        super().__init__(self.state)  # Never attach a URL, token or response body.


def integer(value):
    if isinstance(value, bool) or not re.fullmatch(r"[1-9][0-9]{0,19}", str(value)):
        raise ProbeError()
    return int(value)


def fixture(run_id):
    return ("Harmless NFL LAB private-storage canary; no player, feed, forecast or secret data.\n"
        "run_id=" + str(integer(run_id)) + "; run_attempt=1\n").encode("ascii")


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def network(request, timeout):
    """A fresh no-redirect opener has no cookie jar or ambient Authorization."""
    try:
        return build_opener(ProxyHandler({}), NoRedirect()).open(request, timeout=timeout)
    except HTTPError as response:
        return response


@contextmanager
def request_deadline(enabled):
    """Bound the entire real HTTP exchange, including slow response reads."""
    if not enabled:  # Injected local mocks do not arm process signals.
        yield
        return
    started, old = time.monotonic(), signal.getitimer(signal.ITIMER_REAL)
    if old[0] <= 0 or old[1] != 0 or signal.getsignal(signal.SIGALRM) != signal.SIG_DFL:
        raise ProbeError()
    signal.setitimer(signal.ITIMER_REAL, min(20., old[0]))
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        remaining = old[0] - (time.monotonic() - started)
        if remaining <= 0:
            raise ProbeError()
        signal.setitimer(signal.ITIMER_REAL, remaining)


class Client:
    def __init__(self, token, run_id, *, release_id=None, asset_id=None, transport=None, clock=time.monotonic):
        if not token or not token.startswith("ghs_") or any(ch.isspace() for ch in token):
            raise ProbeError()
        self.token, self.run_id = token, str(integer(run_id))
        self.tag = "lab-private-storage-probe-" + self.run_id + "-1"
        self.release_id = integer(release_id) if release_id is not None else None
        self.asset_id = integer(asset_id) if asset_id is not None else None
        self.control_asset_id = None
        self.transport, self.clock = transport or network, clock
        self.hard_deadline = transport is None
        self.started = clock()
        self.calls = self.transferred = 0
        self.created = self.uploaded = self.draft_pinned = False

    def path(self, suffix):
        return API + "/repos/" + REPOSITORY + suffix

    def browser(self):
        return "https://github.com/" + REPOSITORY + "/releases/download/" + self.tag + "/" + FIXTURE_NAME

    def validate_url(self, url, method, *, cdn=False):
        parts = urlsplit(url)
        if (parts.scheme != "https" or parts.username or parts.password or parts.port is not None
                or parts.fragment or "\\" in url or not parts.path.startswith("/")):
            raise ProbeError()
        if cdn:
            if method != "GET" or parts.hostname not in CDN_HOSTS:
                raise ProbeError()
            return
        allowed = {self.path(""), self.path("/releases/tags/" + self.tag),
            API + "/repos/" + CONTROL_REPO + "/releases/tags/" + CONTROL_TAG}
        if self.release_id:
            allowed |= {self.path("/releases/" + str(self.release_id)), self.path("/releases/" + str(self.release_id) + "/assets")}
        if self.asset_id:
            allowed.add(self.path("/releases/assets/" + str(self.asset_id)))
        if self.control_asset_id:
            allowed.add(API + "/repos/" + CONTROL_REPO + "/releases/assets/" + str(self.control_asset_id))
        browsers = {self.browser(), "https://github.com/" + CONTROL_REPO + "/releases/download/" + CONTROL_TAG + "/" + CONTROL_NAME}
        if method == "GET" and url in allowed | browsers and not parts.query:
            return
        if method == "POST" and url == self.path("/releases") and not self.created:
            return
        upload = "https://uploads.github.com/repos/" + REPOSITORY + "/releases/" + str(self.release_id) + "/assets?name=" + quote(FIXTURE_NAME)
        if method == "POST" and self.draft_pinned and not self.uploaded and url == upload:
            return
        raise ProbeError()

    def request(self, url, *, method="GET", data=None, anonymous=False, octet=False, download=False):
        self.validate_url(url, method)
        # Consume POST reservations BEFORE the transport; ambiguous failures are never repeated.
        if method == "POST":
            if url == self.path("/releases"):
                self.created = True
            else:
                self.uploaded = True
        current = url
        for redirects in range(3):  # At most two redirects; no request retry.
            if self.calls >= MAX_CALLS or self.clock() - self.started >= 120:
                raise ProbeError()
            headers = {"Accept": "application/octet-stream" if octet else "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "nfl-lab-harmless-storage-canary-v1"}
            host = urlsplit(current).hostname
            if not anonymous and host in {"api.github.com", "uploads.github.com"}:
                if host == "api.github.com" and not (current == self.path("") or current.startswith(self.path("") + "/")):
                    raise ProbeError()
                headers["Authorization"] = "Bearer " + self.token
            if data is not None:
                if len(data) > 1024:
                    raise ProbeError()
                headers["Content-Type"] = "application/json" if host == "api.github.com" else "text/plain"
            self.calls += 1
            self.transferred += len(data or b"")
            remaining = MAX_TRANSFER - self.transferred
            if remaining <= 0:
                raise ProbeError()
            try:
                with request_deadline(self.hard_deadline):
                    response = self.transport(Request(current, data=data, headers=headers, method=method),
                        min(20, max(.001, 120 - (self.clock() - self.started))))
                    with response:
                        status = response.status
                        observed = {key.lower(): value for key, value in response.headers.items()}
                        length = observed.get("content-length")
                        if length is not None and (not length.isdigit() or int(length) > min(MAX_RESPONSE, remaining)):
                            raise ProbeError()
                        body = response.read(min(MAX_RESPONSE + 1, remaining))
                        self.transferred += len(body)
                        if len(body) > MAX_RESPONSE or len(body) >= remaining:
                            raise ProbeError()
            except (URLError, OSError, TimeoutError, ValueError):
                raise ProbeError() from None
            if status in {301, 302, 303, 307, 308} and download:
                if method != "GET" or redirects >= 2:
                    raise ProbeError()
                current = observed.get("location", "")
                self.validate_url(current, "GET", cdn=True)
                continue
            return status, observed, body

    def json(self, url, **kwargs):
        status, headers, body = self.request(url, **kwargs)
        expected_status = 201 if kwargs.get("method") == "POST" else 200
        if status != expected_status or headers.get("x-ratelimit-remaining") == "0" or "retry-after" in headers:
            raise ProbeError()
        try:
            result = json.loads(body)
        except (ValueError, UnicodeError):
            raise ProbeError() from None
        if not isinstance(result, dict):
            raise ProbeError()
        return result


def existing_config():
    """Only this exact reviewed harmless destination; no caller-supplied path."""
    path = Path(__file__).resolve().parents[1] / EXISTING_CONFIG_RELATIVE
    if path.is_symlink() or any(parent.is_symlink() for parent in path.parents):
        raise ProbeError()
    payload = path.read_bytes()
    if len(payload) > MAX_SUMMARY or hashlib.sha256(payload).hexdigest() != EXISTING_CONFIG_SHA256:
        raise ProbeError()
    document = json.loads(payload)
    expected_browser = (r"https://github\.com/NickNicky19/NFL-forecasting/releases/download/"
        r"untagged-[0-9a-f]{20}/nfl-lab-private-storage-canary\.txt")
    body = fixture(document["original_run_id"])
    if (document["repository"] != REPOSITORY or document["registration_id"] != "lab-existing-canary-recovery-v1"
            or not re.fullmatch(expected_browser, document["browser_download_url"])
            or len(body) != document["fixture_bytes"] or hashlib.sha256(body).hexdigest() != document["fixture_sha256"]
            or document["asset_name"] != FIXTURE_NAME or document["HTTP_methods"] != ["GET"]):
        raise ProbeError()
    return document


class ExistingClient(Client):
    """Separately versioned GET-only recovery of one already-created canary."""
    def __init__(self, token, active_run_id, *, transport=None, clock=time.monotonic):
        self.config = existing_config()
        self.active_run_id = str(integer(active_run_id))
        if self.active_run_id == self.config["original_run_id"]:
            raise ProbeError()
        self.existing_only = True
        super().__init__(token, self.config["original_run_id"], release_id=self.config["release_id"],
            asset_id=self.config["asset_id"], transport=transport, clock=clock)
        if self.tag != self.config["tag_name"]:
            raise ProbeError()

    def browser(self):
        return self.config["browser_download_url"]

    def validate_url(self, url, method, *, cdn=False):
        if method != "GET":
            raise ProbeError()
        return super().validate_url(url, method, cdn=cdn)


def pin_draft(client, document, *, empty=False):
    release_id = integer(document.get("id"))
    if (client.release_id not in {None, release_id} or document.get("draft") is not True
            or document.get("published_at", "MISSING") is not None or document.get("tag_name") != client.tag
            or document.get("url") != client.path("/releases/" + str(release_id))
            or not isinstance(document.get("assets"), list) or (empty and document["assets"])):
        raise ProbeError("DRAFT_IDENTITY_REQUIRED")
    client.release_id, client.draft_pinned = release_id, True
    return document


def pin_asset(client, document):
    asset_id = integer(document.get("id"))
    body = fixture(client.run_id)
    if (client.asset_id not in {None, asset_id} or document.get("name") != FIXTURE_NAME
            or document.get("url") != client.path("/releases/assets/" + str(asset_id))
            or document.get("browser_download_url") != client.browser()
            or document.get("size") != len(body) or document.get("state") != "uploaded"
            or document.get("digest") not in {None, "sha256:" + hashlib.sha256(body).hexdigest()}
            or (getattr(client, "existing_only", False) and document.get("digest") != "sha256:" + client.config["fixture_sha256"])):
        raise ProbeError("ASSET_IDENTITY_REQUIRED")
    client.asset_id = asset_id
    return document


def pin_single_asset(client, document):
    pin_draft(client, document)
    if len(document["assets"]) != 1:
        raise ProbeError("ASSET_IDENTITY_REQUIRED")
    pin_asset(client, document["assets"][0])


def denial(result):
    status, headers, _ = result
    if 200 <= status < 400:
        raise ProbeError("FAIL_PRIVATE_BOUNDARY")
    if status != 404 or headers.get("x-ratelimit-remaining") == "0" or "retry-after" in headers:
        raise ProbeError("INCONCLUSIVE_DENIAL")


def public_controls(client):
    """Authenticate on our repository; exercise external public routes anonymously."""
    own_repo = client.json(client.path(""))
    if (own_repo.get("full_name") != REPOSITORY or own_repo.get("url") != client.path("")
            or own_repo.get("private") is not False):
        raise ProbeError("PUBLIC_CONTROL_FAILED")
    url = API + "/repos/" + CONTROL_REPO + "/releases/tags/" + CONTROL_TAG
    document = client.json(url, anonymous=True)
    release_id = integer(document.get("id"))
    if (document.get("draft") is not False or not document.get("published_at")
            or document.get("tag_name") != CONTROL_TAG or document.get("url") != API + "/repos/" + CONTROL_REPO + "/releases/" + str(release_id)
            or not isinstance(document.get("assets"), list)):
        raise ProbeError("PUBLIC_CONTROL_FAILED")
    matches = [item for item in document["assets"] if item.get("name") == CONTROL_NAME]
    if len(matches) != 1:
        raise ProbeError("PUBLIC_CONTROL_FAILED")
    asset = matches[0]
    client.control_asset_id = integer(asset.get("id"))
    metadata_url = API + "/repos/" + CONTROL_REPO + "/releases/assets/" + str(client.control_asset_id)
    browser = "https://github.com/" + CONTROL_REPO + "/releases/download/" + CONTROL_TAG + "/" + CONTROL_NAME
    metadata = client.json(metadata_url, anonymous=True)
    if (metadata.get("id") != client.control_asset_id or metadata.get("url") != metadata_url
            or metadata.get("name") != CONTROL_NAME or metadata.get("browser_download_url") != browser or metadata.get("state") != "uploaded"
            or not isinstance(metadata.get("size"), int) or not 0 < metadata["size"] <= MAX_CONTROL_BODY):
        raise ProbeError("PUBLIC_CONTROL_FAILED")
    bodies = []
    for endpoint, octet in ((metadata_url, True), (browser, False)):
        status, headers, body = client.request(endpoint, anonymous=True, octet=octet, download=True)
        if status != 200 or headers.get("x-ratelimit-remaining") == "0" or len(body) != metadata["size"]:
            raise ProbeError("PUBLIC_CONTROL_FAILED")
        bodies.append(body)
    if bodies[0] != bodies[1] or not re.search(rb"[a-fA-F0-9]{64}\s+", bodies[0]):
        raise ProbeError("PUBLIC_CONTROL_FAILED")


def write(client):
    repo = client.json(client.path(""))
    if repo.get("full_name") != REPOSITORY:
        raise ProbeError()
    absent, headers, _ = client.request(client.path("/releases/tags/" + client.tag))
    if absent != 404 or headers.get("x-ratelimit-remaining") == "0" or "retry-after" in headers:
        raise ProbeError()
    body = json.dumps({"tag_name": client.tag, "name": "Harmless LAB storage canary " + client.run_id,
        "body": "Nonsensitive permissions probe only. No NFL data, predictions, secrets or private durability claim.",
        "draft": True, "prerelease": True, "generate_release_notes": False}).encode()
    created = client.json(client.path("/releases"), method="POST", data=body)
    pin_draft(client, created, empty=True)
    expected_upload = "https://uploads.github.com/repos/" + REPOSITORY + "/releases/" + str(client.release_id) + "/assets{?name,label}"
    if created.get("upload_url") != expected_upload:
        raise ProbeError()
    pin_draft(client, client.json(client.path("/releases/" + str(client.release_id))), empty=True)
    pin_asset(client, client.json(expected_upload.removesuffix("{?name,label}") + "?name=" + quote(FIXTURE_NAME),
        method="POST", data=fixture(client.run_id)))
    pin_single_asset(client, client.json(client.path("/releases/" + str(client.release_id))))
    return "WRITE_CANARY_CREATED", {"draft_unpublished": True, "exactly_one_asset": True}


def read(client):
    if not client.release_id or not client.asset_id:
        raise ProbeError()
    public_controls(client)
    checks = {}
    endpoints = {"release_metadata": client.path("/releases/" + str(client.release_id)),
        "asset_metadata": client.path("/releases/assets/" + str(client.asset_id)),
        "asset_list": client.path("/releases/" + str(client.release_id) + "/assets"),
        "api_octet": client.path("/releases/assets/" + str(client.asset_id)), "browser": client.browser()}
    for principal in ("read_only", "anonymous"):
        for label, url in endpoints.items():
            denial(client.request(url, anonymous=principal == "anonymous" or label == "browser", octet=label == "api_octet"))
            key = "anonymous_browser_after_" + principal + "_api_404" if label == "browser" else principal + "_" + label + "_404"
            checks[key] = True
    return "READ_BOUNDARY_DENIED", {"authenticated_own_repo_control": True, "anonymous_public_controls": True, **checks}


def restore(client):
    if not client.release_id or not client.asset_id:
        raise ProbeError()
    pin_single_asset(client, client.json(client.path("/releases/" + str(client.release_id))))
    pin_asset(client, client.json(client.path("/releases/assets/" + str(client.asset_id))))
    status, _, body = client.request(client.path("/releases/assets/" + str(client.asset_id)), octet=True, download=True)
    if status != 200 or body != fixture(client.run_id):
        raise ProbeError("RESTORE_MISMATCH")
    pin_single_asset(client, client.json(client.path("/releases/" + str(client.release_id))))
    return "RESTORE_EXACT_BODY_VERIFIED", {"draft_unpublished": True, "api_exact_body": True,
        "exact_sha256": hashlib.sha256(body).hexdigest() == hashlib.sha256(fixture(client.run_id)).hexdigest(),
        "post_download_draft_single_asset": True}


def pin_existing(client):
    if not isinstance(client, ExistingClient):
        raise ProbeError()
    _, checks = restore(client)
    return "EXISTING_CANARY_PINNED", {**checks, "existing_asset_only": True, "exact_untagged_browser_pinned": True}


def require_existing_pin(client, env):
    expected = {"RECOVERY_PIN_RUN_ID": client.active_run_id, "RECOVERY_PIN_CONFIG_SHA256": EXISTING_CONFIG_SHA256,
        "RELEASE_ID": str(client.release_id), "ASSET_ID": str(client.asset_id), "FIXTURE_SHA256": client.config["fixture_sha256"]}
    if any(env.get(key) != value for key, value in expected.items()):
        raise ProbeError()


def summary(client, state, checks):
    document = {"schema_version": "lab-harmless-storage-probe-v1", "state": state,
        "repository": REPOSITORY, "run_id": client.run_id, "run_attempt": 1,
        "release_id": client.release_id, "asset_id": client.asset_id,
        "fixture_sha256": hashlib.sha256(fixture(client.run_id)).hexdigest(),
        "HTTP_calls": client.calls, "transfer_bytes": client.transferred, "checks": checks,
        "sensitive_data_used": False, "private_durability_qualified": False}
    if isinstance(client, ExistingClient):
        document.update(schema_version="lab-existing-canary-recovery-v1", run_id=client.active_run_id,
            recovery_run_id=client.active_run_id, original_failed_run_id=client.run_id,
            fixture_origin_run_id=client.run_id, recovery_config_sha256=EXISTING_CONFIG_SHA256,
            original_failure_retained=True, existing_asset_only=True)
    encoded = json.dumps(document, sort_keys=True)
    if len(encoded.encode()) > MAX_SUMMARY:
        raise ProbeError()
    return document


def limits():
    resource.setrlimit(resource.RLIMIT_CPU, (120, 120))
    resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))
    signal.signal(signal.SIGALRM, signal.SIG_DFL)
    signal.alarm(120)


def main(argv=None, *, environ=None, transport=None):
    limits()
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("write", "read", "restore", "existing-pin", "existing-read", "existing-restore"))
    parser.add_argument("--release-id")
    parser.add_argument("--asset-id")
    parser.add_argument("--expected-sha256")
    args = parser.parse_args(argv)
    env = os.environ if environ is None else environ
    client = None
    try:
        existing = args.phase.startswith("existing-")
        permission = "read" if args.phase in {"read", "existing-read"} else "write"
        if (env.get("GITHUB_REPOSITORY") != REPOSITORY or env.get("GITHUB_ACTIONS") != "true"
                or env.get("GITHUB_EVENT_NAME") != "workflow_dispatch" or env.get("GITHUB_RUN_ATTEMPT") != "1"
                or env.get("PROBE_PERMISSION") != permission):
            raise ProbeError()
        if existing:
            if env.get("PROBE_MODE") != "storage-probe-existing" or any((args.release_id, args.asset_id, args.expected_sha256)):
                raise ProbeError()
            client = ExistingClient(env.get("GITHUB_TOKEN"), env.get("GITHUB_RUN_ID"), transport=transport)
            if args.phase != "existing-pin":
                require_existing_pin(client, env)
            action = {"existing-pin": pin_existing, "existing-read": read, "existing-restore": restore}[args.phase]
        else:
            client = Client(env.get("GITHUB_TOKEN"), env.get("GITHUB_RUN_ID"), release_id=args.release_id,
                asset_id=args.asset_id, transport=transport)
            expected = hashlib.sha256(fixture(client.run_id)).hexdigest()
            if ((args.phase == "write" and any((args.release_id, args.asset_id, args.expected_sha256)))
                    or (args.phase != "write" and args.expected_sha256 != expected)):
                raise ProbeError()
            action = {"write": write, "read": read, "restore": restore}[args.phase]
        state, checks = action(client)
        result, code = summary(client, state, checks), 0
    except ProbeError as error:
        result, code = (summary(client, error.state, {}) if client else {"state": error.state,
            "sensitive_data_used": False, "private_durability_qualified": False}), 1
    except Exception:
        result, code = (summary(client, "PROBE_INTERNAL_ERROR", {}) if client else {"state": "PROBE_INTERNAL_ERROR"}), 1
    encoded = json.dumps(result, sort_keys=True)
    print(encoded)  # Only bounded, deliberately public-safe fields.
    if env.get("GITHUB_STEP_SUMMARY"):
        with Path(env["GITHUB_STEP_SUMMARY"]).open("a") as stream:
            stream.write("```json\n" + encoded + "\n```\n")
    if code == 0 and env.get("GITHUB_OUTPUT"):
        with Path(env["GITHUB_OUTPUT"]).open("a") as stream:
            keys = ("release_id", "asset_id", "fixture_sha256")
            if isinstance(client, ExistingClient):
                keys += ("recovery_run_id", "recovery_config_sha256")
            for key in keys:
                stream.write(key + "=" + str(result[key]) + "\n")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
