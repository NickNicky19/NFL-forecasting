"""Narrow unchanged positive-control/fixture helpers from the retained probe.
No transport, credential discovery, imports with network effects, or mutation.
"""
import re
from urllib.request import HTTPRedirectHandler
REPOSITORY="NickNicky19/NFL-forecasting"
API="https://api.github.com"
CONTROL_REPO="cli/cli"
CONTROL_TAG="v2.0.0"
CONTROL_NAME="gh_2.0.0_checksums.txt"
MAX_CONTROL_BODY=16384
RESOURCE_PERMISSION_MESSAGE="Resource not accessible by integration"
CDN_HOSTS=frozenset({"release-assets.githubusercontent.com","objects.githubusercontent.com","github-releases.githubusercontent.com"})
class ProbeError(Exception):
    def __init__(self,state="CONTROL_GUARD_STOP"):
        super().__init__(state)


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
