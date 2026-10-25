"""Fictional legal-document bytes and fake HTTP only; no live requests."""
import hashlib
import importlib.metadata
import io
import json
from pathlib import Path
import sys

import pytest
import requests

from nfl_lab import participation_qualification_probe as probe
from nfl_lab.operational_storage import OperationalStorage


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    body = (json.dumps(value, sort_keys=True, allow_nan=False) + "\n").encode()
    path.write_bytes(body)
    return {"path": str(path), "sha256": hashlib.sha256(body).hexdigest()}


class Raw:
    def __init__(self, body, fail_after=None):
        self.stream, self.sizes, self.fail_after = io.BytesIO(body), [], fail_after

    def read(self, size, *, decode_content):
        assert decode_content is False and 0 < size <= 65536
        self.sizes.append(size)
        if self.fail_after is not None and self.stream.tell() >= self.fail_after:
            raise requests.ReadTimeout("fictional partial body timeout")
        return self.stream.read(size)


class Response:
    def __init__(self, body=b"fictional legal documentation", status=200, headers=None, *, known_length=True, fail_after=None):
        self.status_code, self.headers = status, {"Content-Type": "text/html", "ETag": '"fictional"'}
        if known_length:
            self.headers["Content-Length"] = str(len(body))
        self.headers.update(headers or {})
        self.raw, self.url, self.closed = Raw(body, fail_after), None, False

    def __enter__(self):return self
    def __exit__(self, *args):self.closed = True


def prepare(tmp_path, monkeypatch, responses):
    implementation = write_json(tmp_path / "implementation.json", {"budgets": {"HTTP_transactions_including_redirects": 3, "wall_seconds": 60}})
    source_policy = write_json(tmp_path / "source-policy.json", {"storage": {"version": "operational-storage-v2", "limit_bytes": 512 * 1024**2},
        "namespaces": {"private_retention_bytes": 512 * 1024**2}})
    monkeypatch.setattr(probe, "POLICY_SHA256", implementation["sha256"])
    monkeypatch.setattr(probe, "SOURCE_POLICY_SHA256", source_policy["sha256"])
    root = Path(probe.__file__).resolve().parent.parent
    spec = {"registration_id": probe.VERSION, "status": "PREPARED_UNEXECUTED", "implementation_policy": implementation,
        "source_policy": source_policy, "cache": str(tmp_path / "cache"), "output": str(tmp_path / "capture"),
        "terms_url": probe.TERMS_URL, "game_url": probe.GAME_URL, "approved_rights_sha256": [],
        "allowed_terms_redirect_urls": list(probe.REDIRECT_URLS), "budgets": probe.LIMITS.copy(),
        "code_sha256": {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
            for name in ("nfl_lab/participation_qualification_probe.py", "nfl_lab/operational_storage.py")},
        "environment": {"python": sys.version, "executable": sys.executable, "threads": 1,
            "packages": {name: importlib.metadata.version(name) for name in probe.PACKAGES}},
        "prior_capture_review": {"state": "NO_IDENTICAL_INDEXED_CAPTURE_IN_PREVIOUS_BOUNDED_REVIEW"}}
    config = write_json(tmp_path / "execution.json", spec)
    calls, sessions = [], []
    class Session:
        def __enter__(self):sessions.append(self);return self
        def __exit__(self,*args):pass
        def mount(self,prefix,adapter):assert prefix == "https://" and adapter.max_retries.total == 0
        def get(self,url,**kwargs):
            assert (Path(spec["output"]) / "PROBE_CONSUMED.json").exists()
            assert (Path(spec["output"]) / f"private/http/{len(calls)+1:03d}/request-consumed.json").exists()
            assert kwargs["allow_redirects"] is False and kwargs["stream"] is True and kwargs["verify"] is True
            assert kwargs["headers"]["Accept-Encoding"] == "identity" and isinstance(kwargs["auth"], probe._PublicOnlyAuth)
            assert kwargs["timeout"][0] <= 5 and kwargs["timeout"][1] <= 10
            calls.append(url)
            assert len(calls) <= 3 and url in probe.REDIRECT_URLS
            item = responses[len(calls)-1]
            if isinstance(item, BaseException):raise item
            item.url = url
            return item
    monkeypatch.setattr(requests,"Session",Session)
    return config,spec,calls


def test_terms_only_unknown_no_link_or_permission_inference_and_owned_quota(tmp_path,monkeypatch):
    body=b'<html>Fictional terms: permission is not established. <a href="https://www.nfl.com/games/lions-at-chiefs-2023-reg-1">Gamebook</a></html>'
    response=Response(body)
    config,spec,calls=prepare(tmp_path,monkeypatch,[response])
    result=probe.run_probe(config["path"],config["sha256"])
    assert calls == [probe.TERMS_URL] and response.closed
    assert result["state"] == "TERMINAL_RIGHTS_UNKNOWN" and result["rights"] == "UNKNOWN"
    assert result["game_page"] == result["PDF"] == "NOT_REQUESTED" and result["schema_headings"] == "NOT_INSPECTED"
    assert result["usage"]["identity_encoded_and_decoded_body_bytes_received"] == len(body)
    receipt=result["transactions"][0]
    assert receipt["sha256"] == hashlib.sha256(body).hexdigest() and receipt["body_complete"]
    assert receipt["capture_started_utc"] <= receipt["capture_finished_utc"]
    assert receipt["original_publication_utc"] is None and receipt["raw_bytes_hash_matches_counted_chunks"]
    path=Path(spec["output"])/receipt["body_path"]
    storage=OperationalStorage(spec["cache"],json.loads(Path(spec["source_policy"]["path"]).read_text()))
    assert storage.validate_reference(path,receipt["sha256"])["bytes"] == len(body)
    assert not path.stat().st_mode & 0o222
    with pytest.raises(RuntimeError,match="no invocation retry"):
        probe.run_probe(config["path"],config["sha256"])
    assert len(calls)==1


def test_redirect_transactions_charged_and_fixed_three_cap(tmp_path,monkeypatch):
    responses=[Response(b"",302,{"Location":probe.REDIRECT_URLS[1]}),Response(b"",302,{"Location":probe.REDIRECT_URLS[2]}),Response(b"",302,{"Location":probe.REDIRECT_URLS[3]})]
    config,_,calls=prepare(tmp_path,monkeypatch,responses)
    result=probe.run_probe(config["path"],config["sha256"])
    assert len(calls)==3 and result["stop_reason"]=="HTTP_TRANSACTION_LIMIT"
    assert result["usage"]["HTTP_transactions_attempted"]==3


@pytest.mark.parametrize("destination",[probe.GAME_URL,"https://www.nfl.com.evil.test/legal/terms","http://www.nfl.com/legal/terms","https://www.nfl.com/legal/other",probe.TERMS_URL])
def test_redirect_allowlist_and_loops_never_trigger_another_request(tmp_path,monkeypatch,destination):
    config,_,calls=prepare(tmp_path,monkeypatch,[Response(b"",302,{"Location":destination})])
    result=probe.run_probe(config["path"],config["sha256"])
    assert len(calls)==1
    assert result["stop_reason"] in {"REDIRECT_OUTSIDE_EXACT_LEGAL_URL_ALLOWLIST","REDIRECT_LOOP_NO_REPEAT_REQUEST"}


@pytest.mark.parametrize("headers,reason",[({"Content-Encoding":"gzip"},"NONIDENTITY_ENCODING_NOT_CONSUMED"),
    ({"Content-Length":str(1024**2+1)},"DECLARED_BODY_EXCEEDS_REMAINING_CAP"),({"Content-Length":"garbage"},"INVALID_CONTENT_LENGTH")])
def test_encoded_and_declared_byte_limits_stop_before_body_read(tmp_path,monkeypatch,headers,reason):
    response=Response(b"never read",headers=headers)
    config,_,calls=prepare(tmp_path,monkeypatch,[response])
    result=probe.run_probe(config["path"],config["sha256"])
    assert len(calls)==1 and response.raw.sizes==[] and result["stop_reason"]==reason
    assert result["usage"]["identity_encoded_and_decoded_body_bytes_received"]==0


def test_unknown_length_hard_boundary_no_extra_byte_read(tmp_path,monkeypatch):
    response=Response(b"x"*(1024**2+10),known_length=False)
    config,_,_=prepare(tmp_path,monkeypatch,[response])
    result=probe.run_probe(config["path"],config["sha256"])
    assert result["stop_reason"]=="BODY_CAP_BOUNDARY_NO_EXTRA_READ"
    assert response.raw.stream.tell()==1024**2
    assert result["usage"]["identity_encoded_and_decoded_body_bytes_received"]==1024**2
    assert result["transactions"][0]["retained_bytes"]==1024**2


def test_redirect_bodies_share_one_terms_cap(tmp_path,monkeypatch):
    first=Response(b"x"*700000,302,{"Location":probe.REDIRECT_URLS[1]})
    second=Response(b"y"*400000)
    config,_,calls=prepare(tmp_path,monkeypatch,[first,second])
    result=probe.run_probe(config["path"],config["sha256"])
    assert len(calls)==2 and second.raw.sizes==[]
    assert result["usage"]["identity_encoded_and_decoded_body_bytes_received"]==700000
    assert result["stop_reason"]=="DECLARED_BODY_EXCEEDS_REMAINING_CAP"


def test_partial_transport_failure_retains_owned_body_request_receipt_and_no_retry(tmp_path,monkeypatch):
    response=Response(b"x"*100000,fail_after=65536)
    config,spec,calls=prepare(tmp_path,monkeypatch,[response])
    with pytest.raises(probe._CaptureFailure):probe.run_probe(config["path"],config["sha256"])
    output=Path(spec["output"])
    receipt=json.loads((output/'private/http/001/response-receipt.json').read_text())
    assert receipt["received_body_bytes"]==receipt["retained_bytes"]==65536 and not receipt["body_complete"]
    assert (output/receipt["body_path"]).read_bytes()==b"x"*65536
    assert (output/'PROBE_FAILURE.json').exists() and json.loads((output/'PROBE_FINISHED.json').read_text())["state"]=="FAILED"
    assert len(calls)==1


def test_connection_failure_no_retry_and_403_terminal_unknown(tmp_path,monkeypatch):
    config,spec,calls=prepare(tmp_path,monkeypatch,[requests.ConnectionError("fictional blocked request")])
    with pytest.raises(requests.ConnectionError):probe.run_probe(config["path"],config["sha256"])
    assert len(calls)==1 and (Path(spec['output'])/'PROBE_FAILURE.json').exists()
    other=tmp_path/'other';other.mkdir()
    config,_,calls=prepare(other,monkeypatch,[Response(b"fictional denied",403)])
    assert probe.run_probe(config['path'],config['sha256'])["stop_reason"]=="HTTP_STATUS_NOT_200"
    assert len(calls)==1


@pytest.mark.parametrize("field,value",[("approved_rights_sha256",["a"*64]),("terms_url",probe.GAME_URL),("allowed_terms_redirect_urls",[probe.GAME_URL])])
def test_v1_cannot_be_widened_by_config_or_fake_clearance(tmp_path,monkeypatch,field,value):
    config,spec,calls=prepare(tmp_path,monkeypatch,[])
    spec[field]=value
    config=write_json(Path(config['path']),spec)
    with pytest.raises(ValueError):probe.run_probe(config['path'],config['sha256'])
    assert not calls and not Path(spec['output']).exists()


def test_auth_handler_does_not_add_credentials():
    request=requests.Request('GET',probe.TERMS_URL,auth=probe._PublicOnlyAuth()).prepare()
    assert 'Authorization' not in request.headers
