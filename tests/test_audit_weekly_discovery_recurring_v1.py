"""Two fictional current runs on frozen code; real native protocol, GET only."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import socket

import pytest

from nfl_lab import audit_weekly_discovery_v1 as d, audit_weekly_retained_v1 as retained
from nfl_lab import private_draft_store as store
import test_audit_weekly_discovery_v1 as old
import test_audit_weekly_retained_v1 as historical
from test_audit_weekly_discovery_v1 import original


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    monkeypatch.setattr(socket.socket, "connect", lambda *_: pytest.fail("REAL_NETWORK_FORBIDDEN"))


def current(monkeypatch, identifier):
    for module in (old, historical):
        monkeypatch.setattr(module, "CURRENT_SOURCE", old.SOURCE)
        monkeypatch.setattr(module, "CURRENT_RUN", identifier)


def test_two_new_runs_on_unchanged_code_discover_and_restore_originals(original, tmp_path, monkeypatch):
    original_handoff = store.canonical(original.reader)
    current_identities = []
    for n in range(2):
        identifier = str(49900000001 + n); current(monkeypatch, identifier)
        c = old.case(original, tmp_path / str(n))
        factory, transport = c.factory, c.history.transport
        def fresh_factory(operation):
            client = factory(operation); client.process = str(8 + n) * 64
            return client
        def current_job(request, timeout):
            response = transport(request, timeout)
            if request.full_url == store.API + '/actions/runs/' + identifier + '/jobs?per_page=100&page=1':
                import json
                body = json.loads(response.body); body['jobs'][0]['id'] = 9001 + n
                return old.Response(body)
            return response
        c.factory = fresh_factory; c.history.transport = current_job
        discovered = old.execute(c); discovered.verify()
        current_identities.append(discovered.document['current'])
        assert discovered.document["current"]["source_sha"] == original.receipt["source_sha"]
        assert discovered.document["current"]["run_id"] == identifier != original.receipt["run_id"]
        assert store.canonical(discovered.document["reader_handoff"]) == original_handoff
        request = retained.prepare_request(old.ROOT, discovered.document["reader_handoff"], c.history.old.package,
            exporter_api_job_id=discovered.document["exporter_api_job_id"], historical_source_sha256=c.pins,
            cache=c.p.base / "cache", state_root=c.p.base / "state", output=c.output.parent / "retained",
            pending_census=c.history.old.census)
        request["approved"] = True
        stamp = datetime.now(timezone.utc)
        authority = dict(schema_version=retained.VERSION + "-native-authority", phase=retained.PHASE,
            request_sha256=store.sha(store.canonical(request)), repository=store.REPO, owner_root_go_sha256="f" * 64,
            owner_root_checked=True, actual_actions_api_authenticated=True, api_job_id=9001 + n, source_sha=old.SOURCE,
            run_id=identifier, run_attempt=1, job_id=old.CURRENT_JOB, workflow_ref=old.WORKFLOW,
            issued_at_utc=stamp.isoformat(), expires_at_utc=(stamp + timedelta(minutes=15)).isoformat(),
            fits=0, remote_writes=0, protected_outcome_reads=0, public_release=False)
        restored = retained.restore(request, c.factory, storage=c.p.storage, authority=authority, root=old.ROOT)
        assert restored["current"]["source_sha"] == restored["original_archive"]["source_sha"]
        assert store.canonical(restored["original_reader_handoff"]) == original_handoff
        for name, ref in restored["aliases"].items():
            assert Path(ref["path"]).read_bytes() == Path(restored["original_physical_bindings"][name]["path"]).read_bytes()
        assert all(p["run_id"] == identifier and p["source_sha"] == old.SOURCE for p in restored["current_restore_proofs"])
        assert all(p["run_id"] == old.RUN and p["source_sha"] == old.SOURCE for p in restored["historical_reader_witness"]["proofs"])
        assert restored["remote_writes"] == restored["model_decodes"] == restored["protected_outcome_reads"] == 0
        assert all(q.method == "GET" for q in c.history.calls)
    for key in ('run_id','api_job_id','process_identity'):
        assert current_identities[0][key] != current_identities[1][key]


@pytest.mark.parametrize("failure", ["same_run", "producer_process", "reader_process", "reused_api_job"])
def test_same_code_cannot_reuse_old_run_job_or_process(original, tmp_path, monkeypatch, failure):
    current(monkeypatch, old.RUN if failure == "same_run" else "49900000003")
    c = old.case(original, tmp_path)
    factory = c.factory
    def changed(operation):
        client = factory(operation)
        if failure == "producer_process": client.process = original.reader["archive"]["producer"]["process_identity"]
        if failure == "reader_process": client.process = original.reader["restorer"]["process_identity"]
        return client
    c.factory = changed
    if failure == "reused_api_job":
        transport = c.history.transport
        def wrong_job(request, timeout):
            response = transport(request, timeout)
            if request.full_url == store.API + "/actions/runs/" + old.CURRENT_RUN + "/jobs?per_page=100&page=1":
                import json
                body = json.loads(response.body); body["jobs"][0]["id"] = original.reader["archive"]["producer"]["api_job_id"]
                return old.Response(body)
            return response
        c.history.transport = wrong_job
    expected = "FRESH_CROSS_RUN_DISCOVERY_CONTEXT" if failure == "same_run" else "FRESH_DISCOVERY_API_JOB" if failure == "reused_api_job" else "FRESH_DISCOVERY_PROCESS"
    with pytest.raises(store.StoreError, match=expected): old.execute(c)
    private_ids = {original.reader["archive"]["index_descriptor"]["entry"]["payload_asset_id"],
                   original.reader["witness_descriptor"]["entry"]["payload_asset_id"]}
    assert not old.payload_gets(c) & private_ids
    assert not (c.output / "DISCOVERED.json").exists()
