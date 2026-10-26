"""Fictional split source inventories; no network or serialized authority grants."""
from copy import deepcopy
from pathlib import Path
import socket

import pytest

from nfl_lab import audit_weekly_controller_bootstrap_v1 as b
from nfl_lab import audit_weekly_controller_registration_v1 as w
from nfl_lab import audit_weekly_controller_v1 as c
from test_audit_weekly_controller_bootstrap_v1 import system, locator_system
from test_audit_weekly_controller_registration_v1 import case, controller_system, writer_reader, PHASES
from test_audit_weekly_parent_v1 import case as parent_case
import test_audit_weekly_controller_v1 as old


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("REAL_NETWORK_FORBIDDEN")
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)


def main_workflow():
    # Main has its own reviewed workflow and no native Producer jobs.
    return (b"on:\n  schedule:\n    - cron: '36 13,14 * * *'\n  workflow_dispatch: {}\n"
        b"concurrency:\n  group: nfl-lab-single-writer\n  cancel-in-progress: false\n"
        b"jobs:\n  lab:\n    permissions:\n      contents: write\n      actions: write\n    steps: []\n")


@pytest.fixture
def separate_case(case):
    parent = {name: case.pins[name] for name in b.PARENT_EXECUTABLE_PINS}
    bodies = {name: (case.source / name).read_bytes() for name in parent}
    bodies[c.WORKFLOW] = main_workflow()
    bodies["nfl_lab/state.py"] = b"FICTIONAL Main's original state validators remain distinct"
    parent.update({name: c.sha(body) for name, body in bodies.items()})
    case.root["effective_epoch"].update(schema_version=w.SEPARATE_CONTEXT_SCHEMA, parent_code_pins=parent)
    tree_url = c.API + "/git/trees/" + "1" * 40 + "?recursive=1"
    case.data[tree_url]["tree"] = [dict(path=name, mode="100644", type="blob", sha=c.blob_sha(body))
        for name, body in bodies.items()]
    for name, body in bodies.items():
        case.data[c.contents_url(name, old.A)] = old.content(name, body)
    case.parent_pins, case.parent_bodies, case.parent_tree_url = parent, bodies, tree_url
    return case


def test_native_registration_seals_distinct_maps_and_own_workflow_hashes(separate_case):
    x = separate_case
    _, _, inputs = writer_reader(x)
    sealed = x.execute(PHASES[2], inputs)
    p = sealed.docs["registration"]
    assert p["parent"]["code_pins"] == x.parent_pins
    assert p["producer"]["code_pins"] == x.pins
    assert p["parent"]["source_sha"] == old.A and p["producer"]["source_sha"] == old.B
    assert p["parent"]["workflow_sha256"] == c.sha(main_workflow()) != p["producer"]["workflow_sha256"]
    assert p["parent"]["code_pins"]["nfl_lab/state.py"] != p["producer"]["code_pins"]["nfl_lab/state.py"]
    assert not set(w.FILES) & set(x.parent_pins)
    assert all(p["parent"]["code_pins"][n] == p["producer"]["code_pins"][n] for n in b.SHARED_EXECUTABLE_PINS)
    assert set(b.SHARED_EXECUTABLE_PINS) <= set(x.pins)
    assert len(x.parent_pins) <= 128 and len(x.pins) <= 128
    assert sealed.docs["safe_seal"]["code_pins_sha256"] == c.digest(x.pins)
    assert sealed.docs["safe_seal"]["registration_sha256"] == c.digest(p)
    assert all(len(stage.call.request["code_pins"]) <= 128 for stage in (sealed,))


@pytest.mark.parametrize("damage", ["parent_blob", "parent_body", "producer_blob", "wrong_commit", "shared_pin", "workflow_pin", "symlink_mode"])
def test_split_source_mismatches_fail_before_private_io(separate_case, damage):
    x = separate_case
    if damage == "parent_blob":
        next(n for n in x.data[x.parent_tree_url]["tree"] if n["path"] == "nfl_lab/state.py")["sha"] = "0" * 40
    elif damage == "parent_body":
        x.data[c.contents_url("nfl_lab/state.py", old.A)] = old.content("nfl_lab/state.py", b"FICTIONAL corrupt body")
    elif damage == "producer_blob":
        x.data[c.API + "/git/trees/" + "2" * 40 + "?recursive=1"]["tree"][0]["sha"] = "0" * 40
    elif damage == "wrong_commit":
        x.data[x.parent_tree_url]["sha"] = "3" * 40
    elif damage == "shared_pin":
        x.parent_pins["nfl_lab/private_draft_probe_helpers.py"] = "0" * 64
    elif damage == "workflow_pin":
        x.parent_pins[c.WORKFLOW] = "0" * 64
    elif damage == "symlink_mode":
        x.data[x.parent_tree_url]["tree"][0]["mode"] = "120000"
    error = b.BootstrapError if damage == "shared_pin" else w.RegistrationError
    code = {"shared_pin": "BOOTSTRAP_AND_FROZEN_CONTROLLER_MUST_BE_SOURCE_PINNED",
        "wrong_commit": "COMPLETE_LITERAL_REGISTRATION_SOURCE_TREE",
        "symlink_mode": "PLAIN_ROLE_LOCAL_PINNED_SOURCE_BLOB"}.get(damage,
        "ROLE_LOCAL_PINNED_BYTES_MUST_MATCH_LITERAL_COMMIT")
    with pytest.raises(error, match=code):
        x.execute(PHASES[0])
    assert not any("/releases/" in request.full_url for request in x.server.calls)
    assert all(request.get_method() == "GET" for request in x.server.calls)


def test_each_inventory_has_its_own_unchanged_128_pin_cap(separate_case):
    go = deepcopy(separate_case.root)
    for role in ("parent", "producer"):
        changed = deepcopy(go)
        pins = changed["effective_epoch"]["parent_code_pins"] if role == "parent" else changed["code_pins"]
        for i in range(129 - len(pins)):
            pins["nfl_lab/fictional_extra_" + str(i) + ".py"] = "1" * 64
        with pytest.raises(w.RegistrationError, match="COMPLETE_BOUNDED_REGISTRATION_SOURCE_PINS"):
            w.prepare_template(changed, separate_case.readiness)


@pytest.mark.parametrize("name", sorted(b.SHARED_EXECUTABLE_PINS))
def test_every_shared_dependency_is_required_and_identical(separate_case, name):
    parent, producer = w._source_specs(separate_case.root)
    for role in ("parent", "producer"):
        pp, cp = deepcopy(parent), deepcopy(producer)
        (pp if role == "parent" else cp)["code_pins"].pop(name)
        with pytest.raises(b.BootstrapError, match="BOUNDED_ROLE_LOCAL_SOURCE_INVENTORY"):
            b.source_inventories(pp, cp)
    pp = deepcopy(parent)
    pp["code_pins"][name] = "0" * 64
    with pytest.raises(b.BootstrapError, match="BOOTSTRAP_AND_FROZEN_CONTROLLER_MUST_BE_SOURCE_PINNED"):
        b.source_inventories(pp, producer)


def test_parent_bootstrap_never_installs_producer_only_sources(locator_system):
    x = locator_system
    private = "nfl_lab/fictional_numerical_only.py"
    body = b"FICTIONAL Producer-only source, never imported"
    (x.child_source / private).write_bytes(body)
    x.p["producer"]["code_pins"][private] = c.sha(body)
    state = x.parent_source / "nfl_lab/state.py"
    state.write_bytes(b"FICTIONAL Main state remains original")
    x.p["parent"]["code_pins"]["nfl_lab/state.py"] = c.sha(state.read_bytes())
    (x.parent_source / c.WORKFLOW).write_bytes(main_workflow())
    x.p["parent"]["code_pins"][c.WORKFLOW] = c.sha(main_workflow())
    x.p["parent"]["workflow_sha256"] = c.sha(main_workflow())
    x.reg = c.canonical(x.p); x.seal = c.sha(x.reg)
    x.native.update(registration_sha256=x.seal, code_pins_sha256=c.digest(x.p["producer"]["code_pins"]))
    x.publish_locator()
    env = dict(x.env, GITHUB_SHA=old.A, GITHUB_JOB=x.p["parent"]["job_id"])
    seal = b.load_seal(env, x.parent_source, metadata_get=x.get, clock=lambda: old.AT,
        read_head=x.read_head, registry_version=2)
    assert seal.registration_bytes == x.reg and not (x.parent_source / private).exists()
    assert "nfl_lab/state.py" not in x.p["producer"]["code_pins"]
    assert len(x.calls) == 10
    state.write_bytes(b"FICTIONAL source race after registration")
    with pytest.raises(c.ControllerError, match="CURRENT_CODE_INVENTORY_MISMATCH"):
        b.load_seal(env, x.parent_source, metadata_get=x.get, clock=lambda: old.AT,
            read_head=x.read_head, registry_version=2)


def test_full_parent_uses_producer_sidecar_pins_with_main_own_state_and_workflow(parent_case):
    x = parent_case.x
    producer_pins = deepcopy(x.p["producer"]["code_pins"])
    parent_pins = {name: x.p["parent"]["code_pins"][name] for name in b.PARENT_EXECUTABLE_PINS}
    for name in set(x.p["parent"]["code_pins"]) - set(parent_pins):
        (x.parent_source / name).unlink()
    state = x.parent_source / "nfl_lab/state.py"
    state.write_bytes(b"FICTIONAL Main's separately reviewed original state")
    parent_pins["nfl_lab/state.py"] = c.sha(state.read_bytes())
    workflow = main_workflow().replace(c.CADENCE["cron"].encode(), c.PARENT_CADENCE["cron"].encode())
    (x.parent_source / c.WORKFLOW).write_bytes(workflow)
    parent_pins[c.WORKFLOW] = c.sha(workflow)
    x.p["parent"].update(code_pins=parent_pins, workflow_sha256=c.sha(workflow))
    x.api.data[c.contents_url(c.WORKFLOW, old.A)] = old.content(c.WORKFLOW, workflow)
    parent_case.reseal()
    result = parent_case.execute()
    dispatched = c.decode(parent_case.service.dispatch_body["inputs"]["inference_builder_go_json"])
    assert result["state"] == "ENQUEUE_ONCE_AND_EXIT" and result["dispatches"] == 1
    assert dispatched["code_pins"] == producer_pins == x.p["producer"]["code_pins"]
    assert not (x.parent_source / "nfl_lab/audit_weekly_grade_v1.py").exists()
    assert parent_pins["nfl_lab/state.py"] != producer_pins["nfl_lab/state.py"]
    assert result["child_completion_claimed"] is result["activation_authorized"] is False
