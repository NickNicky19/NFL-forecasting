"""Fictional immutable state and local Git only; no labels or network."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
from pathlib import Path
import subprocess

import pytest

from nfl_lab import publication_qualification as q, publication_scope as p
from nfl_lab.state import digest, records, save

NOW = datetime(2030, 1, 1, tzinfo=timezone.utc)
POLICY = "a" * 64


def stamp(minutes):
    return (NOW + timedelta(minutes=minutes)).isoformat()


def git(root, *args):
    return p._git(root, *args).decode().strip()


def fixture(tmp_path, *, row_change=None, binding_change=None, header_change=None,
            persist_change=None, web_persist_change=None, publish=10, web=True, duplicate_binding=False):
    root = tmp_path / "repo"; root.mkdir()
    git(root, "init", "-b", "main")
    state = root / "state"
    row = {"player_id": "00-0000001", "game_id": "fictional-game", "target": "rec",
           "model_id": "fictional-fixed", "season": 2030, "week": 7, "period": "REG",
           "scoring_id": "half_ppr", "team": "AAA", "opponent": "BBB", "position": "WR",
           "sleeper_id": "001", "feature_cutoff_utc": stamp(0), "issued_at": stamp(1),
           "kickoff_utc": stamp(60), "code_integrity": "pre_post_source_digest_required",
           "code_sha256": "c" * 64, "input_sha256": "d" * 64,
           "prediction_functional": "conditional_played_mean", "mean": 3.0}
    row.update(row_change or {})
    batch = save(state, "forecasts", {"schema_version": "lab-forecast-batch-v1",
        "persist_started_at": stamp(2), "rows": [row], "missed": []})
    persistence = {"batch": batch, "completed_at": stamp(3), "late_games": []}
    persistence.update(persist_change or {})
    save(state, "persistence", persistence)
    binding = {k: row[k] for k in ("season", "week", "period", "scoring_id", "game_id", "sleeper_id",
                                  "target", "team", "opponent", "position", "kickoff_utc")}
    binding.update({"lab_player_id": row["player_id"], "lab_model_id": row["model_id"],
                    "lab_issued_at": row["issued_at"], "lab_feature_cutoff_utc": row["feature_cutoff_utc"],
                    "lab_forecast_sha256": digest(row), "method": "raw_sleeper", "value_sha256": "e" * 64})
    binding.update(binding_change or {})
    header = {"generated_at": stamp(-2), "observed_at": stamp(-1), "season": 2030, "week": 7}
    header.update(header_change or {})
    snapshot = None
    if web:
        snapshot = save(state, "website_bindings", {"schema_version": "website-point-bindings-v1",
            "lab_batch": batch, "persist_started_at": stamp(4), "header": header,
            "rows": [binding, deepcopy(binding)] if duplicate_binding else [binding]})
        persistence = {"snapshot": snapshot, "completed_at": stamp(5), "late_games": []}
        persistence.update(web_persist_change or {})
        save(state, "website_persistence", persistence)
    git(root, "add", "state")
    git(root, "-c", "user.name=fictional", "-c", "user.email=test@example.invalid", "commit", "-m", "fictional capture")
    commit = git(root, "rev-parse", "HEAD")
    files = {f"forecasts/{batch}.json.gz": hashlib.sha256((state / "forecasts" / (batch + ".json.gz")).read_bytes()).hexdigest()}
    if web:
        files[f"website_bindings/{snapshot}.json.gz"] = hashlib.sha256((state / "website_bindings" / (snapshot + ".json.gz")).read_bytes()).hexdigest()
    scope = p.scope_document(commit, files, verified_remote_commit=commit, policy_sha256=POLICY)
    selected = p.verify_committed_scope(root, state, commit=commit, scope=scope, policy_sha256=POLICY)
    receipts = {}
    for kind, key, document, evidence in selected:
        field = "batch" if kind == "forecasts" else "snapshot"
        timely = sum(p.utc(r["kickoff_utc"]) > p.utc(stamp(publish)) for r in document["rows"])
        receipts[kind] = {field: key, "commit": commit, "verified_remote_commit": commit,
            "publication_scope_schema": p.SCHEMA, "publication_scope_sha256": digest(scope),
            "observed_remote_readback_at": stamp(publish), "timely_rows": timely,
            "late_rows": len(document["rows"]) - timely, **evidence, "scope": "fictional"}
    return {"root": root, "state": state, "batch": batch, "snapshot": snapshot, "row": row,
            "binding": binding, "scope": scope, "receipts": receipts,
            "evidence": {digest(scope): scope}}


def append(f, *, changes=None, skip=()):
    for kind, receipt in f["receipts"].items():
        if kind not in skip:
            r = deepcopy(receipt); r.update((changes or {}).get(kind, {}))
            save(f["state"], "publication" if kind == "forecasts" else "website_publication", r)


def forecast(f, scopes=None):
    return q.qualified_forecast_view(f["root"], f["state"], f["evidence"] if scopes is None else scopes, POLICY)


def website(f, scopes=None):
    return q.qualified_website_view(f["root"], f["state"], f["evidence"] if scopes is None else scopes, POLICY)


def test_complete_private_views_are_copied_deterministic_and_do_not_write(tmp_path):
    f = fixture(tmp_path); append(f)
    before = {str(p): p.read_bytes() for p in f["state"].rglob("*.json.gz")}
    rows, receipt = forecast(f)
    assert len(rows) == 1 and rows[0]["row"] == f["row"]
    assert rows[0]["qualification"]["publication_receipt_sha256"] == digest(f["receipts"]["forecasts"])
    assert receipt["expected_source_policy_sha256"] == POLICY
    assert receipt["qualification_policy_sha256"] == q.QUALIFICATION_POLICY_SHA256
    assert len(receipt["qualifier_code_sha256"]) == 64
    web, web_receipt = website(f)
    assert len(web) == 1 and web[0]["binding"] == f["binding"]
    assert web_receipt["qualified_rows"] == {"forecasts": 1, "website_bindings": 1}
    assert website(f) == (web, web_receipt)
    rows[0]["row"]["team"] = "changed"; web[0]["binding"]["team"] = "changed"
    assert forecast(f)[0][0]["row"]["team"] == "AAA"
    assert before == {str(p): p.read_bytes() for p in f["state"].rglob("*.json.gz")}
    assert receipt["scientific_confirmation"] == "NOT_DETERMINED_BY_PUBLICATION_QUALIFICATION"


def test_missing_full_scope_is_unavailable_never_reconstructed(tmp_path):
    f = fixture(tmp_path); append(f)
    rows, receipt = forecast(f, {})
    assert rows == [] and receipt["unqualified_row_reasons"] == {"SCOPE_EVIDENCE_UNAVAILABLE": 1}
    assert website(f, {})[0] == []


def test_legacy_cannot_qualify_or_suppress_new_actual_late_clock(tmp_path):
    f = fixture(tmp_path, publish=60)
    old = {"batch": f["batch"], "commit": "0" * 40, "observed_remote_readback_at": stamp(-100)}
    key = save(f["state"], "publication", old)
    path = f["state"] / "publication" / (key + ".json.gz"); body = path.read_bytes()
    assert forecast(f)[0] == []
    append(f)
    rows, receipt = forecast(f)
    assert rows == [] and receipt["legacy_receipts_unqualified"] == {"forecasts": 1}
    assert "INCONSISTENT_OR_LATE_CLOCK_CHAIN" in receipt["unqualified_row_reasons"]
    assert path.read_bytes() == body


def test_legacy_early_receipt_does_not_block_timely_scoped_proof(tmp_path):
    f = fixture(tmp_path)
    save(f["state"], "publication", {"batch": f["batch"], "observed_remote_readback_at": stamp(-10)})
    append(f)
    assert forecast(f)[0][0]["qualification"]["observed_remote_readback_at"] == stamp(10)


def test_earliest_valid_clock_then_receipt_digest_is_selected(tmp_path):
    f = fixture(tmp_path); append(f)
    for minute, scope_text in [(20, "later"), (10, "same clock other receipt")]:
        r = {**f["receipts"]["forecasts"], "observed_remote_readback_at": stamp(minute), "scope": scope_text}
        save(f["state"], "publication", r)
    rows, _ = forecast(f)
    candidates = [r for r in records(f["state"], "publication") if r["observed_remote_readback_at"] == stamp(10)]
    assert rows[0]["qualification"]["publication_receipt_sha256"] == min(map(digest, candidates))


@pytest.mark.parametrize("field,value", [
    ("commit", "HEAD"), ("commit", "A" * 40), ("verified_remote_commit", "0" * 40),
    ("state_path", "forecasts/../x"), ("file_sha256", "0" * 64), ("git_blob_oid", "0" * 40),
    ("publication_scope_sha256", "bad"), ("timely_rows", True), ("timely_rows", 0),
    ("late_rows", 1), ("snapshot", "f" * 64), ("observed_remote_readback_at", "not a clock")])
def test_contradictory_scoped_receipt_fails_closed_even_beside_valid(tmp_path, field, value):
    f = fixture(tmp_path); append(f)
    append(f, changes={"forecasts": {field: value}}, skip=("website_bindings",))
    rows, receipt = forecast(f)
    assert rows == []
    assert receipt["unqualified_row_reasons"] == {"CONTRADICTORY_PUBLICATION_EVIDENCE": 1}


@pytest.mark.parametrize("change", [{"completed_at": stamp(1)}, {"late_games": ["fictional-game"]}])
def test_persistence_clock_and_late_game_counters_are_checked(tmp_path, change):
    f = fixture(tmp_path, persist_change=change); append(f)
    assert forecast(f)[1]["unqualified_row_reasons"] == {"INVALID_PERSISTENCE_EVIDENCE": 1}


def test_distinct_persistence_receipts_are_not_digest_order_selected(tmp_path):
    f = fixture(tmp_path); append(f)
    save(f["state"], "persistence", {"batch": f["batch"], "completed_at": stamp(4), "late_games": []})
    assert forecast(f)[1]["unqualified_row_reasons"] == {"CONTRADICTORY_PERSISTENCE_EVIDENCE": 1}


@pytest.mark.parametrize("original_scoped", [False, True])
def test_cross_batch_conflicts_never_replace_an_original_opportunity(tmp_path, original_scoped):
    f = fixture(tmp_path, web=False)
    if original_scoped:
        append(f)
    else:
        save(f["state"], "publication", {"batch": f["batch"], "observed_remote_readback_at": stamp(9)})
    later_row = {**f["row"], "issued_at": stamp(2), "mean": 4.0}
    later = save(f["state"], "forecasts", {"schema_version": "lab-forecast-batch-v1",
        "persist_started_at": stamp(3), "rows": [later_row], "missed": []})
    save(f["state"], "persistence", {"batch": later, "completed_at": stamp(4), "late_games": []})
    git(f["root"], "add", "state")
    git(f["root"], "-c", "user.name=f", "-c", "user.email=f@example.invalid", "commit", "-m", "conflicting later capture")
    commit = git(f["root"], "rev-parse", "HEAD")
    name = f"forecasts/{later}.json.gz"
    scope = p.scope_document(commit, {name: hashlib.sha256((f["state"] / name).read_bytes()).hexdigest()},
                             verified_remote_commit=commit, policy_sha256=POLICY)
    evidence = p.verify_committed_scope(f["root"], f["state"], commit=commit, scope=scope, policy_sha256=POLICY)[0][3]
    f["evidence"][digest(scope)] = scope
    save(f["state"], "publication", {**f["receipts"]["forecasts"], "batch": later,
        "commit": commit, "verified_remote_commit": commit, "publication_scope_sha256": digest(scope), **evidence})
    rows, receipt = forecast(f)
    assert rows == []
    assert receipt["unqualified_row_reasons"]["CONTRADICTORY_ROW_IDENTITY"] == (2 if original_scoped else 1)


def test_distinct_model_opportunities_in_separate_batches_are_preserved(tmp_path):
    f = fixture(tmp_path, web=False); append(f)
    other = save(f["state"], "forecasts", {"schema_version": "lab-forecast-batch-v1",
        "persist_started_at": stamp(2), "rows": [{**f["row"], "model_id": "other-model"}], "missed": []})
    assert other != f["batch"]
    assert len(forecast(f)[0]) == 1


@pytest.mark.parametrize("change,reason", [
    ({"feature_cutoff_utc": stamp(2)}, "INCONSISTENT_OR_LATE_CLOCK_CHAIN"),
    ({"issued_at": stamp(3)}, "INCONSISTENT_OR_LATE_CLOCK_CHAIN"),
    ({"code_integrity": "unverified"}, "SOURCE_INTEGRITY_UNAVAILABLE"),
    ({"code_sha256": "bad"}, "SOURCE_INTEGRITY_UNAVAILABLE"),
    ({"prediction_functional": q.POINT_SHADOW}, "POINT_SHADOW_UNQUALIFIED")])
def test_capture_chain_integrity_and_point_shadow_remain_unqualified(tmp_path, change, reason):
    f = fixture(tmp_path, row_change=change); append(f)
    assert forecast(f)[1]["unqualified_row_reasons"] == {reason: 1}


@pytest.mark.parametrize("change", [{"lab_forecast_sha256": "0" * 64}, {"lab_player_id": "wrong"},
                                    {"lab_issued_at": stamp(0)}, {"team": "ZZZ"},
                                    {"kickoff_utc": stamp(61)}, {"value_sha256": "bad"}])
def test_website_requires_exact_qualified_lab_link(tmp_path, change):
    f = fixture(tmp_path, binding_change=change); append(f)
    assert website(f)[0] == []


def test_website_requires_both_publications_before_any_rehydration(tmp_path):
    f = fixture(tmp_path); append(f, skip=("forecasts",))
    assert website(f)[0] == []


def test_website_capture_and_header_clocks_are_checked(tmp_path):
    f = fixture(tmp_path, header_change={"observed_at": stamp(1)}); append(f)
    assert website(f)[1]["unqualified_row_reasons"] == {"INCONSISTENT_OR_LATE_WEBSITE_CLOCK_CHAIN": 1}


@pytest.mark.parametrize("change", [{"season": 2031}, {"week": 8}])
def test_website_header_context_must_match_linked_row(tmp_path, change):
    f = fixture(tmp_path, header_change=change); append(f)
    assert website(f)[1]["unqualified_row_reasons"] == {"CONTRADICTORY_WEBSITE_LINK": 1}


def test_duplicate_website_method_binding_is_quarantined(tmp_path):
    f = fixture(tmp_path, duplicate_binding=True); append(f)
    assert website(f)[1]["unqualified_row_reasons"] == {"CONTRADICTORY_WEBSITE_LINK": 2}


@pytest.mark.parametrize("mutation", ["local", "symlink", "scope_digest", "policy", "omitted", "wrong_tree"])
def test_reuses_exact_scope_commit_file_proof(tmp_path, mutation):
    f = fixture(tmp_path); append(f)
    path = f["state"] / "forecasts" / (f["batch"] + ".json.gz")
    if mutation == "local":
        # Well-formed immutable local document, but not the committed bytes.
        original = path.read_bytes(); path.write_bytes(original + b"changed")
    elif mutation == "symlink":
        other = f["root"] / "other"; other.write_bytes(path.read_bytes()); path.unlink(); path.symlink_to(other)
    elif mutation == "scope_digest":
        f["scope"]["files"] = {}
    elif mutation == "policy":
        f["scope"]["policy_sha256"] = "f" * 64
        changed = digest(f["scope"]); f["evidence"] = {changed: f["scope"]}
        append(f, changes={"forecasts": {"publication_scope_sha256": changed}})
    elif mutation == "omitted":
        f["scope"]["files"].pop(f"forecasts/{f['batch']}.json.gz")
        changed = digest(f["scope"]); f["evidence"] = {changed: f["scope"]}
        append(f, changes={"forecasts": {"publication_scope_sha256": changed}})
    else:
        git(f["root"], "rm", "-r", "--cached", "state")
        git(f["root"], "-c", "user.name=f", "-c", "user.email=f@example.invalid", "commit", "-m", "wrong tree")
        commit = git(f["root"], "rev-parse", "HEAD")
        f["scope"].update(commit=commit, verified_remote_commit=commit)
        changed = digest(f["scope"]); f["evidence"] = {changed: f["scope"]}
        append(f, changes={"forecasts": {"publication_scope_sha256": changed, "commit": commit, "verified_remote_commit": commit}})
    try:
        rows, _ = forecast(f)
    except (ValueError, OSError):
        rows = []
    assert rows == []


def test_no_outcomes_http_models_or_scoring_imports_or_calls(tmp_path, monkeypatch):
    f = fixture(tmp_path); append(f)
    import nfl_lab.state as state_module
    monkeypatch.setattr(state_module, "resolved_outcomes", lambda *a: pytest.fail("labels forbidden"))
    calls = []
    original = subprocess.run
    def local_git_only(args, *a, **kw):
        assert args[:2] == ["git", "--no-replace-objects"]
        assert not any(x in args for x in ("fetch", "pull", "push", "ls-remote"))
        calls.append(args)
        return original(args, *a, **kw)
    monkeypatch.setattr(subprocess, "run", local_git_only)
    assert len(website(f)[0]) == 1 and calls
    source = Path(q.__file__).read_text()
    assert "resolved_outcomes" not in source and "requests" not in source
    assert "website_baselines" not in source and "models" not in source


@pytest.mark.parametrize("policy", [None, "bad", "A" * 64])
def test_explicit_source_policy_version_required(tmp_path, policy):
    f = fixture(tmp_path)
    with pytest.raises(ValueError, match="explicit policy"):
        q.qualified_forecast_view(f["root"], f["state"], f["evidence"], policy)
