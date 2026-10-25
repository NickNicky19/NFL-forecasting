"""A grading failure or source race cannot publish a successful forecast feed."""
from copy import deepcopy

import pytest

from nfl_lab import audit_weekly_delivery_v1 as delivery, private_draft_store as store, gha_private_checkpoint as cp
from test_audit_weekly_delivery_v1 import original, packet, deliver, BASE


def metadata(receipt):
    return dict(schema_version="audit-weekly-grading-delivery-v1", feed_sha256=receipt["feed_sha256"],
        sidecar_sha256="a" * 64, evidence_descriptor_sha256="b" * 64,
        sidecar_path="controller-v1/grade-checkpoints/" + receipt["feed_sha256"] + ".json.gz")


def test_feed_publishes_only_after_successful_grading_delivery(packet):
    q = packet; sequence = []; publisher = q.publisher; original_bytes = dict(q.original_files)
    def grading(receipt):
        assert q.published == []
        assert receipt["root_go_sha256"] == "d" * 64
        sequence.append("durable-grading")
        return metadata(receipt)
    def publish(*args, **kwargs):
        assert sequence == ["durable-grading"]
        sequence.append("feed")
        return publisher(*args, **kwargs)
    result = deliver(q, before_publication=grading, publisher=publish)
    assert sequence == ["durable-grading", "feed"]
    assert result["grading_checkpoint"]["feed_sha256"] == result["feed_sha256"]
    assert result["state"] == "PUBLIC_DERIVED_DELIVERY_COMPLETE" and len(q.source_observations) == 4
    assert q.original_files == original_bytes


@pytest.mark.parametrize("failure", ["exception", "missing", "private", "different_feed"])
def test_failed_or_malformed_grading_delivery_retains_failure_and_publishes_no_feed(packet, failure):
    q = packet
    def grading(receipt):
        if failure == "exception": raise RuntimeError("FICTIONAL_PRIVATE_ERROR_MUST_NOT_ENTER_PUBLIC_OUTPUT")
        value = metadata(receipt)
        if failure == "missing": value.pop("sidecar_sha256")
        if failure == "private": value["private_outcomes"] = "FICTIONAL_NEVER_PUBLIC"
        if failure == "different_feed": value["feed_sha256"] = "0" * 64
        return value
    with pytest.raises(store.StoreError, match="^GRADING_DELIVERY_FAILED_FEED_NOT_PUBLISHED$"):
        deliver(q, before_publication=grading)
    assert q.published == []
    failed = (q.base / "delivery/DELIVERY_FAILED.json").read_bytes()
    assert cp.strict_json(failed)["state"] == "GRADING_DELIVERY_FAILED_FEED_NOT_PUBLISHED"
    assert b"FICTIONAL_PRIVATE" not in failed and b"private_outcomes" not in failed


def test_source_change_during_grading_stops_feed_publication(packet):
    q = packet; calls = []
    def source(client, branch):
        calls.append(branch)
        return q.policy["source_sha"] if len(calls) < 3 else "0" * 40
    with pytest.raises(store.StoreError, match="^PRODUCER_SOURCE_CHANGED_AFTER_GRADING_BEFORE_FEED$"):
        deliver(q, source_check=source, before_publication=metadata)
    assert q.published == [] and len(calls) == 3


@pytest.mark.parametrize("operation,callback", [("RECURRING_CAPTURE", None), ("CURRENT_CORRECTION_CAPTURE", metadata)])
def test_production_root_requires_the_matching_grading_path_before_native_restore(packet, operation, callback):
    q = packet
    root = dict(publication=True, approved=True, repository=store.REPO, source_sha=q.policy["source_sha"], operation=operation)
    calls = []
    def forbidden(operation):
        calls.append(operation)
        raise AssertionError("RESTORE_OR_POST_BEFORE_CLOSED_ROOT_ROUTE")
    with pytest.raises(store.StoreError, match="^RECURRING_PUBLICATION_REQUIRES_NATIVE_GRADING_DELIVERY$"):
        delivery.deliver(q.reader_handoff, q.package, forbidden, q.storage, q.base / "delivery", store.sha(store.canonical(root)),
            q.pending_census, q.configuration, q.publication_root, expected_source_sha=q.policy["source_sha"],
            expected_original_choice_sha256=q.policy["origin_choice_sha256"], root_go=root, before_publication=callback,
            source_policy_path=BASE / "config/operational-source-policy-v2.json")
    assert calls == [] and q.published == []
