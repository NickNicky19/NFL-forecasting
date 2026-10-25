"""Fictional integrated archive/API and fake publisher; no real services/Git."""
from copy import deepcopy
from contextlib import redirect_stdout
from datetime import timedelta
import importlib.util
import gzip
import io
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import urlsplit,parse_qs

import pytest

from nfl_lab import audit_weekly_delivery_v1 as delivery,audit_weekly_archive_v1 as archive
from nfl_lab import private_draft_store as store,gha_private_checkpoint as cp,audit_weekly_public_v1 as public
from tools import audit_weekly_delivery_v1 as cli,persist_state

BASE=Path(archive.__file__).resolve().parents[1]
# Always use fixtures belonging to the actually imported integrated source,
# including its R0 control-completion/clock and public-policy contracts.
sys.path.insert(0,str(BASE/"tests"))
spec=importlib.util.spec_from_file_location("_delivery_integrated_public_fixture",BASE/"tests/test_audit_weekly_public_v1.py")
fixture_module=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture_module)


@pytest.fixture(scope="module")
def original(tmp_path_factory):
    base=tmp_path_factory.mktemp("delivery-fictional-original")
    collect=archive.collect
    def complete_origin(root,context,*,storage,output,**kwargs):
        # The public helper's fictional old completion is retained, but its
        # initial generic archive fixture has only a dummy witness. Archive
        # that SAME fixture-generated receipt here; no actual missing receipt
        # is invented and no protected/model/outcome bytes are opened.
        raw=archive.read_owned(storage,context["original_choice"],raw=True)
        choice=cp.strict_json(raw);frozen=public.feed.utc(choice["actual_frozen_at"])
        receipt=dict(schema_version="weekly-generic-future-producer-v1-weekly-choice-completion",
            choice_binding=dict(path="/fictional/original/choice",bytes=len(raw),sha256=store.sha(raw)),
            persisted_completed_at=(frozen+timedelta(seconds=1)).isoformat(),original_predeadline_completion=None)
        e=archive.read_owned(storage,context["epoch"])
        assert public.feed.digest(receipt)==e["original"]["completion_sha256"]
        ref=archive.write(storage,base/"fictional-retained-origin-completion.json",receipt)
        return collect(root,dict(context,origin_witness=ref),storage=storage,output=output,**kwargs)
    rights=dict(schema_version="FICTIONAL_ORIGINAL_REGISTERED_RIGHTS",source_policy_sha256=cp.POLICY_SHA,derived_selected_only=True)
    write=archive.write
    def declared_rights(storage,path,value):
        if Path(path)==base/"public-context/public_policy.json":value["rights_authorities"]=[public.feed.digest(rights)]
        return write(storage,path,value)
    with patch.object(archive,"collect",side_effect=complete_origin),patch.object(archive,"write",side_effect=declared_rights):
        q=fixture_module.build_packet(base)
    q.original_rights=rights
    q.reader_handoff=cp.strict_json((base/"reader/READER_HANDOFF.json").read_bytes())
    q.original_files={n:cp.read_ref(r) for n,r in q.consumed["aliases"].items()}
    return q


@pytest.fixture
def packet(original,tmp_path):
    q=SimpleNamespace(**vars(original));q.base=tmp_path;q.storage.register_root(tmp_path)
    q.configuration=dict(policy=deepcopy(original.policy),r0=deepcopy(original.r0),rights_authority=deepcopy(original.original_rights))
    q.factory=q.service.factory(tmp_path/"delivery-journal","consume");q.published=[];q.source_observations=[]
    q.publication_root=tmp_path/"fictional-source-repository";q.publication_root.mkdir()
    q.old_public=q.storage.register_root(tmp_path/"fictional-public-history")
    q.storage.write_bytes(q.old_public/"prior-observation.json",b"FICTIONAL_IMMUTABLE_OLD_HISTORY")
    def publish(root,state,**kwargs):
        assert kwargs["storage"] is q.storage and kwargs["metadata_policy"] is True
        assert root==q.publication_root and kwargs["policy_path"]==BASE/"config/operational-source-policy-v2.json"
        feed,receipt=persist_state.public_export_names(kwargs["files"])
        receipt_doc=cp.strict_json(gzip.decompress((state/receipt).read_bytes()))
        assert set(receipt_doc)==delivery.RECEIPT_KEYS and receipt_doc["schema_version"]==delivery.VERSION+"-public-receipt"
        assert receipt_doc["rights_authority_sha256"]==public.feed.digest(q.configuration["rights_authority"])
        assert receipt_doc["feed_sha256"]==kwargs["files"][feed]
        assert receipt=="public/weekly-adaptive-v1/receipts/"+kwargs["files"][feed]+".json.gz"
        assert kwargs["files"][receipt]==store.sha((state/receipt).read_bytes())
        assert receipt_doc["policy_registered_at_utc"]==q.configuration["policy"]["registered_at_utc"]
        assert receipt_doc["workflow_sha256"]==q.configuration["policy"]["workflow_sha256"]
        assert len(kwargs["files"])==2
        q.published.append(dict(state=state,files=dict(kwargs["files"])))
        for name,digest in kwargs["files"].items():q.storage.import_file(state/name,q.old_public/name,expected_sha256=digest)
        assert (q.old_public/"prior-observation.json").read_bytes()==b"FICTIONAL_IMMUTABLE_OLD_HISTORY"
    q.publisher=publish
    def source(client,branch):
        assert client.process==q.client.process and branch==q.policy["source_branch"]
        q.source_observations.append(branch);return q.policy["source_sha"]
    q.source=source
    return q


def deliver(q,**changes):
    kwargs=dict(expected_source_sha=q.policy["source_sha"],expected_original_choice_sha256=q.policy["origin_choice_sha256"],
        source_policy_path=BASE/"config/operational-source-policy-v2.json",source_check=q.source,publisher=q.publisher)
    kwargs.update(changes)
    return delivery.deliver(q.reader_handoff,q.package,q.factory,q.storage,q.base/"delivery","d"*64,q.pending_census,q.configuration,q.publication_root,**kwargs)


def test_real_consume_typed_epoch_live_export_exact_two_files_and_immutable_history(packet):
    q=packet
    with patch.object(persist_state,"validate_public_export",side_effect=AssertionError("old verifier must remain unused")):
        result=deliver(q)
    assert result["state"]=="PUBLIC_DERIVED_DELIVERY_COMPLETE" and len(q.published)==1 and len(q.source_observations)==3
    assert result["feed_path"] in q.published[0]["files"] and result["export_receipt_path"] in q.published[0]["files"]
    assert result["source_sha"]==q.policy["source_sha"] and result["categories"]==["pass_att"]
    receipt=cp.strict_json((q.base/"delivery/DELIVERY_RECEIPT.json").read_bytes())
    assert receipt["source_head_verified_before_after"] is True and set(receipt["jobs"])=={"produce","restore","consume"}
    assert {v["api_job_id"] for v in receipt["jobs"].values()}=={777,778,779}
    assert not {"aliases","weights","forecast_value","player_id","controls","runtime_binding","path"}&set(receipt)
    assert result["delivery_receipt_sha256"]==store.sha(store.canonical(receipt))
    consumed=cp.strict_json((q.base/"delivery/consumed/RESTORED.json").read_bytes())
    public_receipt=cp.strict_json(gzip.decompress((q.published[0]["state"]/result["export_receipt_path"]).read_bytes()))
    terminal=archive.read_owned(q.storage,consumed["aliases"]["runtime/FINISHED.json"])
    expected=dict(archive_index_sha256=consumed["index_sha256"],archive_files_sha256=consumed["files_sha256"],
        reader_witness_sha256=q.reader_handoff["witness_descriptor"]["entry"]["payload"]["sha256"],
        epoch_sha256=terminal["epoch_sha256"],choice_sha256=terminal["choice_sha256"])
    assert set(public_receipt)==delivery.RECEIPT_KEYS
    assert public_receipt["policy_registered_at_utc"]==q.policy["registered_at_utc"]
    assert public.feed.utc(public_receipt["policy_registered_at_utc"])<public.feed.utc(public_receipt["created_at"])
    assert all(public_receipt[key]==receipt[key]==result[key]==value for key,value in expected.items())
    assert all(p["process_identity"]==q.client.process for p in consumed["exporter_proofs"])
    for name,raw in q.original_files.items():assert cp.read_ref(q.consumed["aliases"][name])==raw
    assert (q.root/"selected.jsonl.gz").read_bytes()==q.original_bytes


@pytest.mark.parametrize("change",["rights","r0","source","original_choice","root_sha","explicit_private_root"])
def test_pinned_authority_mismatch_stops_before_consume_or_publisher(packet,change):
    q=packet;kwargs={}
    if change=="rights":q.configuration["rights_authority"]={"unregistered":True}
    elif change=="r0":q.configuration["r0"]["deployment_id"]=0
    elif change=="source":kwargs["expected_source_sha"]="0"*40
    elif change=="original_choice":kwargs["expected_original_choice_sha256"]="0"*64
    elif change=="root_sha":q.reader_handoff=deepcopy(q.reader_handoff);q.reader_handoff["archive"]["root_go_sha256"]="0"*64
    else:kwargs["root_go"]=dict(publication=False)
    with pytest.raises(store.StoreError):deliver(q,**kwargs)
    assert not q.published and not q.factory.clients


def test_source_moves_before_publication_keeps_reviewable_files_and_publishes_nothing(packet):
    q=packet;values=iter([q.policy["source_sha"],"0"*40])
    with pytest.raises(store.StoreError,match="PRODUCER_SOURCE_CHANGED_BEFORE_PUBLICATION"):
        deliver(q,source_check=lambda *_:next(values))
    assert not q.published
    assert (q.base/"delivery/DELIVERY_PUBLISH_INTENT.json").exists()
    assert list((q.base/"delivery/public-state/public/weekly-adaptive-v1").rglob("*.json"))


def test_source_race_after_publication_preserves_raced_bytes_and_fails_without_retry(packet):
    q=packet;values=iter([q.policy["source_sha"],q.policy["source_sha"],"0"*40])
    with pytest.raises(store.StoreError,match="PRODUCER_SOURCE_CHANGED_AFTER_PUBLICATION"):
        deliver(q,source_check=lambda *_:next(values))
    assert len(q.published)==1 and not (q.base/"delivery/DELIVERY_RECEIPT.json").exists()
    failure=cp.strict_json((q.base/"delivery/DELIVERY_FAILED.json").read_bytes())
    assert failure["state"]=="SOURCE_RACE_AFTER_PUBLICATION_BYTES_RETAINED"
    assert (q.old_public/failure["feed_path"]).is_file()


def test_unresolved_source_after_publication_does_not_undo_or_retry(packet):
    q=packet;calls=[]
    def source(*_):
        calls.append(1)
        if len(calls)==3:raise RuntimeError("PRIVATE_LIBRARY_PATH_AND_TOKEN")
        return q.policy["source_sha"]
    with pytest.raises(store.StoreError,match="PRODUCER_SOURCE_RECHECK_UNRESOLVED_AFTER_PUBLICATION"):deliver(q,source_check=source)
    assert len(q.published)==1
    assert b"PRIVATE_LIBRARY" not in (q.base/"delivery/DELIVERY_FAILED.json").read_bytes()


def test_publisher_failure_retains_owned_pair_and_sanitizes_library_text(packet):
    q=packet
    def fail(*args,**kwargs):raise RuntimeError("PRIVATE_LIBRARY_PATH_AND_TOKEN")
    with pytest.raises(store.StoreError,match="PUBLIC_DELIVERY_PUBLICATION_FAILED_BYTES_RETAINED"):deliver(q,publisher=fail)
    assert (q.base/"delivery/DELIVERY_PUBLISH_INTENT.json").exists()
    assert b"PRIVATE_LIBRARY" not in (q.base/"delivery/DELIVERY_FAILED.json").read_bytes()


def test_changed_before_values_policy_cannot_be_registered_after_capture(packet):
    q=packet;q.configuration["policy"]["rights_authorities"].append("0"*64)
    with pytest.raises(store.StoreError,match="EXACT_ARCHIVED_BEFORE_VALUES_PUBLIC_POLICY"):deliver(q)
    assert not q.published


def test_default_source_check_is_one_bounded_GET_and_exact_repo_branch():
    calls=[]
    class Client:
        allowed=set()
        def json(self,url):calls.append(url);return dict(ref="refs/heads/research/fictional",object=dict(type="commit",sha="a"*40))
    assert delivery.source_head(Client(),"research/fictional")=="a"*40
    assert delivery.source_head(Client(),"research/fictional")=="a"*40
    assert len(calls)==2 and calls[0]!=calls[1]
    assert all(urlsplit(u).path.endswith("/git/ref/heads/research/fictional") for u in calls)
    assert all(set(parse_qs(urlsplit(u).query))=={"audit_weekly_delivery_nonce"} for u in calls)
    with pytest.raises(store.StoreError):delivery.source_head(Client(),"../other")


def test_native_factory_cap_and_default_repository_guard_fail_before_client_creation(packet):
    q=packet
    with patch.object(archive,"MAX_CLIENTS",0),pytest.raises(store.StoreError,match="DELIVERY_NATIVE_CLIENT_CAP"):deliver(q)
    assert not q.factory.clients
    q.base=q.base/"different-output";q.base.mkdir()
    with pytest.raises(store.StoreError,match="ACTUAL_PUBLICATION_REPOSITORY_SOURCE_REQUIRED"):deliver(q,publisher=None)
    assert not q.factory.clients


def test_standalone_entrypoint_cannot_reload_or_manufacture_live_delivery():
    for argv in ([],["--execute"]):
        output=io.StringIO()
        with redirect_stdout(output):assert cli.main(argv)==2
        assert "IN_PROCESS_AUTHENTICATED_EXPORTER_REQUIRED" in output.getvalue()
