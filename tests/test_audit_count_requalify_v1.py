"""Fictional retained state only: no fit, HTTP, label read or private asset access."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import io
import json
from pathlib import Path
import subprocess
import os
import sys

import joblib
import numpy as np
import pandas as pd
import pytest

from nfl_lab import audit_count_requalify_v1 as audit
from nfl_lab import gha_private_checkpoint as cp
from nfl_lab import weekly_future_inference as future
from nfl_lab.cdf_engine import SupportPrior
from nfl_lab.operational_storage import OperationalStorage
from nfl_lab.role_boosting import RoleCountBoostingModel
from nfl_lab.state import digest
from tools import audit_count_requalify_v1 as cli

ROOT = Path(__file__).resolve().parents[1]


def test_native_restore_envelope_accepts_the_unchanged_real_exchange_guard():
    # A separate interpreter owns the hard native caps; no HTTP/model I/O occurs.
    code = '''
from pathlib import Path
from nfl_lab import audit_count_requalify_v1 as audit, private_draft_store as store
import signal
plan={"runtime_envelopes":audit.shared_envelopes()}
with audit.resource_envelope(plan,"restore",Path.cwd()):
    assert signal.getsignal(signal.SIGALRM)==signal.SIG_DFL
    assert signal.getitimer(signal.ITIMER_REAL)[0]>0
    with store.exchange_deadline(True):
        pass
print("NATIVE_RESTORE_EXCHANGE_ACCEPTED")
'''
    numerical=json.loads((ROOT/'config/weekly-owner-private-bootstrap-v1.json').read_text())['numerical_environment']
    result=subprocess.run([sys.executable,'-B','-c',code],cwd=ROOT,env={**os.environ,**numerical},
                          text=True,capture_output=True,timeout=30)
    assert result.returncode==0,result.stderr
    assert result.stdout.strip()=='NATIVE_RESTORE_EXCHANGE_ACCEPTED'


class FixedEstimator:
    classes_ = np.array([0., 1.])

    def predict(self, design):
        return np.full(len(design), 5.5)

    def predict_proba(self, design):
        return np.tile([.75, .25], (len(design), 1))

    def fit(self, *args, **kwargs):
        raise AssertionError("zero-fit recovery attempted estimator fitting")


class FixedDesign:
    def transform(self, frame):
        return np.zeros((len(frame), 1))

    def fit(self, *args, **kwargs):
        raise AssertionError("zero-fit recovery attempted design fitting")


def legacy_module(tmp_path):
    body = subprocess.run(["git", "show", audit.ORIGINAL_SOURCE + ":nfl_lab/weekly_future_inference.py"],
        cwd=ROOT, check=True, capture_output=True).stdout
    (tmp_path / "original-weekly_future_inference.py").write_bytes(body)
    plan = dict(original_source=dict(name="original-weekly_future_inference.py", bytes=len(body), sha256=audit.sha(body)))
    return audit.load_original_module(tmp_path, plan)


def fictional_model():
    category = dict(target="rush_att", state="READY", support="count", modeled_roles=["RB"], primary_roles=["RB"],
        panels={"base": ["f_player_rush_att_mean3"], "context": ["f_player_rush_att_mean3"]})
    return RoleCountBoostingModel(category, "A", estimators={"pooled": FixedEstimator()},
        designs={"pooled": FixedDesign()}, priors={"RB": SupportPrior("count", q=.75), "FB": SupportPrior("count", q=.5)},
        global_prior=SupportPrior("count", q=.8), audit={"subfits": []})


def fictional_fixture(model, family="count_A"):
    frame = pd.DataFrame([dict(season=2025, week=1, game_id="fictional-game", player_id=str(i),
        team="A", opponent="B", position=role, kickoff_utc="2025-09-07T13:00:00Z", cutoff_utc="2025-09-07T12:00:00Z",
        feature_max_source_available_utc="2025-09-06T00:00:00Z", f_player_games_prior=games,
        f_player_rush_att_mean3=2.) for i, (role, games) in enumerate([("RB", 4.), ("RB", 0.), ("FB", 0.), ("unknown", 0.)])],
        index=[91, 22, 74, 15])
    return future.query_projection(frame, future.model_contract(model, family)[1])


def old_recipe(contract, family="count_A"):
    return digest(dict(registration="weekly-adaptive-release-v1", family=family, source_contract=contract,
        code_pins=audit.ORIGINAL_PINS, category_contract_sha256="9154f113d75b8b6af3cbc21e0c407e7af4b79b29e53a288d487a2dc868473de4",
        training_rule="annual earlier seasons since2019; fixed correction earlierOOF since2022; pass_td context/pass_att intercept initially",
        fallback="existing role/global priors; all offered preserved"))


def retained(tmp_path, module, *, target="rush_att", family="count_A", storage=None, root=None):
    policy = json.loads((ROOT / "config/operational-source-policy-v2.json").read_text())
    storage = storage or OperationalStorage(tmp_path / "cache", policy, state=tmp_path / "state")
    root = root or tmp_path / "owned"
    storage.register_root(root)
    model = fictional_model()
    model.category = deepcopy(model.category)
    model.category["target"] = target
    if family != "count_A":
        from nfl_lab.cdf_engine import LeafCDFModel
        from nfl_lab.direct_boosters import DirectBoosterModel
        support = "bernoulli" if target == "anytime_td" else "signed_integer" if target.endswith("_yd") else "count"
        model.category["support"] = support
        prior = SupportPrior(support, q=.75, center=2, p=.4)
        if family == "leaf_cdf_base":
            model = LeafCDFModel(model.category, "base", None, None, np.array([0., 1.]), priors={"RB": prior}, global_prior=prior)
        else:
            model = DirectBoosterModel(model.category, "base", design=FixedDesign(), estimator=FixedEstimator(),
                priors={"RB": prior}, global_prior=prior, audit={"fit_state": "FITTED"}, library="catboost", complexity="medium")
    frame = fictional_fixture(model, family)
    expected = module.prediction_bits(model, family, frame)
    stream = io.BytesIO()
    joblib.dump(dict(model=model, fixture=frame, expected_bits=expected, base_artifact_sha256=None), stream, compress=3)
    storage.write_bytes(root / "original-trained.joblib", stream.getvalue())
    model_ref = cp.binding(root / "original-trained.joblib")
    contract = dict(source_policy_sha256=cp.POLICY_SHA, feature_builder_sha256="f" * 64, availability_rule="fictional-asof")
    m = dict(schema_version=future.VERSION, artifact_kind="TRAINED_FUTURE_QUERY_NOT_HISTORICAL_REPLAY",
        family=family, method_id={"count_A": "COUNT_A", "leaf_cdf_base": "LAB_CDF", "catboost_medium": "CATBOOST_MEDIUM"}[family],
        category=model.category, features=future.model_contract(model, family)[1],
        code_pins=audit.ORIGINAL_PINS, environment=future.environment(), source_contract=contract, model=model_ref,
        dependencies=[], fit_receipt=dict(training_started_at="2024-01-01T00:00:00Z", training_completed_at="2024-01-02T00:00:00Z"),
        fit_clock_status="RECORDED", procedure_version=old_recipe(contract, family),
        replay_fixture_sha256=future.frame_digest(frame), replay_bits_sha256=digest(expected),
        training_cutoff_utc="2025-01-01T00:00:00Z", training_frame_sha256="a" * 64,
        training_max_available_utc="2023-12-01T00:00:00Z", artifact_created_at="2025-01-01T00:00:00Z")
    storage.write_bytes(root / "original-future-inference.json", audit.canonical(m))
    storage.write_bytes(root / "RESTORE_RECEIPT.json", audit.canonical(dict(fictional=True)))
    return storage, root, m, cp.binding(root / "original-future-inference.json"), model_ref, cp.binding(root / "RESTORE_RECEIPT.json")


def test_original_replay_then_new_loader_preserves_warm_bits_and_originals(tmp_path, monkeypatch):
    module = legacy_module(tmp_path)
    storage, root, old_manifest, original_ref, model_ref, proof_ref = retained(tmp_path, module)
    original_json, original_model = Path(original_ref["path"]).read_bytes(), Path(model_ref["path"]).read_bytes()
    monkeypatch.setattr(RoleCountBoostingModel, "fit", lambda *a, **k: pytest.fail("new model fit"))
    monkeypatch.setattr(SupportPrior, "fit", lambda *a, **k: pytest.fail("new prior fit"))
    result = audit.requalify_one(original_ref, model_ref, storage=storage, destination=root / "effective",
        original_module=module, plan_sha256="b" * 64, restore_receipt=proof_ref)
    assert result["comparison"]["warm_rows"] == 1
    assert result["comparison"]["fallback_rows"] == 3
    assert result["comparison"]["warm_bits_identical"]
    assert result["current_loader_replay_passed"]
    assert result["fits"] == 0
    assert len(result["prior_probes"]) >= 3
    effective = json.loads(Path(result["manifest"]["path"]).read_text())
    assert effective["count_fallback_version"] == future.COUNT_A_FALLBACK_VERSION
    assert effective["procedure_version"] != old_manifest["procedure_version"]
    for field in ("fit_receipt", "training_cutoff_utc", "training_max_available_utc", "training_frame_sha256", "replay_fixture_sha256", "artifact_created_at"):
        assert effective[field] == old_manifest[field]
    assert Path(original_ref["path"]).read_bytes() == original_json
    assert Path(model_ref["path"]).read_bytes() == original_model
    assert (root / "effective/original-trained.joblib").read_bytes() == original_model
    bundle = joblib.load(effective["model"]["path"])
    values, reasons = future._points(bundle["model"], "count_A", bundle["fixture"])
    np.testing.assert_allclose(values, [5.5, 3., 1., 4.])
    assert reasons[0] == ""
    old_bundle = joblib.load(io.BytesIO(original_model))
    assert module.prediction_bits(old_bundle["model"], "count_A", old_bundle["fixture"]) == old_bundle["expected_bits"]


@pytest.mark.parametrize("change,expected", [("environment", "ORIGINAL_CODE_ENVIRONMENT"),
    ("source", "SOURCE_AND_ORIGINAL_MODEL_HASH"), ("code", "ORIGINAL_CODE_ENVIRONMENT"),
    ("model_hash", "SOURCE_AND_ORIGINAL_MODEL_HASH"), ("recipe", "ORIGINAL_PROCEDURE")])
def test_bad_metadata_rejected_before_model_decode(tmp_path, monkeypatch, change, expected):
    module = legacy_module(tmp_path)
    storage, root, m, _, model_ref, proof_ref = retained(tmp_path, module)
    m = deepcopy(m)
    if change == "environment":
        m["environment"]["numpy"] = "fictional-wrong"
    elif change == "source":
        m["source_contract"]["source_policy_sha256"] = "c" * 64
    elif change == "code":
        m["code_pins"]["role_boosting.py"] = "d" * 64
    elif change == "model_hash":
        m["model"]["sha256"] = "e" * 64
    else:
        m["procedure_version"] = "f" * 64
    storage.write_bytes(root / "bad-manifest.json", audit.canonical(m))
    monkeypatch.setattr(joblib, "load", lambda *a, **k: pytest.fail("decode before metadata checks"))
    with pytest.raises(ValueError, match=expected):
        audit.requalify_one(cp.binding(root / "bad-manifest.json"), model_ref, storage=storage,
            destination=root / "effective", original_module=module, plan_sha256="b" * 64, restore_receipt=proof_ref)
    assert not (root / "effective").exists()


def test_nonowned_model_rejected_before_decode(tmp_path, monkeypatch):
    module = legacy_module(tmp_path)
    storage, root, _, original_ref, model_ref, proof_ref = retained(tmp_path, module)
    rogue = tmp_path / "rogue.joblib"
    rogue.write_bytes(Path(model_ref["path"]).read_bytes())
    rogue.chmod(0o444)
    monkeypatch.setattr(joblib, "load", lambda *a, **k: pytest.fail("unowned model decode"))
    with pytest.raises(ValueError):
        audit.requalify_one(original_ref, cp.binding(rogue), storage=storage, destination=root / "effective",
            original_module=module, plan_sha256="b" * 64, restore_receipt=proof_ref)


def test_replay_bit_mismatch_preserves_failed_evidence_and_writes_no_effective(tmp_path):
    module = legacy_module(tmp_path)
    storage, root, m, _, model_ref, proof_ref = retained(tmp_path, module)
    m["replay_bits_sha256"] = "0" * 64
    storage.write_bytes(root / "bad-replay.json", audit.canonical(m))
    with pytest.raises(ValueError, match="ORIGINAL_REPLAY_BITS"):
        audit.requalify_one(cp.binding(root / "bad-replay.json"), model_ref, storage=storage,
            destination=root / "effective", original_module=module, plan_sha256="b" * 64, restore_receipt=proof_ref)
    assert (root / "bad-replay.json").is_file()
    assert not (root / "effective").exists()


def test_warm_bit_change_is_rejected(tmp_path, monkeypatch):
    module = legacy_module(tmp_path)
    model = fictional_model()
    frame = fictional_fixture(model)
    original = future._points
    def wrong(*args):
        values, reasons = original(*args)
        values[reasons == ""] = np.nextafter(values[reasons == ""], np.inf)
        return values, reasons
    monkeypatch.setattr(future, "_points", wrong)
    with pytest.raises(ValueError, match="WARM_PREDICTION_BITS_CHANGED"):
        audit.compare_points(model, "count_A", frame, module)


def test_absent_supported_prior_remains_abstention(tmp_path):
    module = legacy_module(tmp_path)
    model = fictional_model()
    model.priors.clear()
    model.global_prior = None
    result = audit.compare_points(model, "count_A", fictional_fixture(model), module)
    assert result["fallback_rows"] == 4
    assert result["warm_rows"] == 0


def test_oracle_does_not_trust_the_production_prior_mean_property(tmp_path, monkeypatch):
    module = legacy_module(tmp_path)
    model = fictional_model()
    fixture = fictional_fixture(model)
    # q=.75 independently means3. The lower median remains2. A mutually wrong
    # repaired predictor/property must not turn the audit into a tautology.
    monkeypatch.setattr(SupportPrior, "mean", property(lambda self: 123.))
    with pytest.raises(audit.AuditGuardError, match="STORED_PRIOR_MEAN_REQUIRED"):
        audit.compare_points(model, "count_A", fixture, module)


def test_original_source_tamper_fails_before_import(tmp_path):
    body = b"raise RuntimeError('must not execute')"
    (tmp_path / "original-weekly_future_inference.py").write_bytes(body)
    with pytest.raises(ValueError, match="ORIGINAL_SOURCE_HASH"):
        audit.load_original_module(tmp_path, dict(original_source=dict(name="original-weekly_future_inference.py", bytes=len(body), sha256=audit.sha(body))))


def test_no_execute_has_no_input_reads(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(audit, "read_bytes", lambda *a: pytest.fail("preparation must not read"))
    assert cli.main(["restore", "--package", str(tmp_path / "missing")]) == 2
    assert "PREPARATION_ONLY_NO_IO" in capsys.readouterr().out


def test_failed_cli_redacts_exception_and_library_output(capsys, monkeypatch):
    def fail(*args, **kwargs):
        print("private fictional row and signed URL")
        raise RuntimeError("private fictional row and credential")
    monkeypatch.setattr(audit, "prepare_package", fail)
    assert cli.main(["prepare", "--inventory", "fictional", "--output", "fictional"]) == 1
    output = capsys.readouterr()
    assert "private fictional" not in output.out + output.err
    assert json.loads(output.out)["reason"] == "COUNT_REQUALIFICATION_GUARD_OR_OPERATION_FAILED"


@pytest.mark.parametrize("error,expected", [
    (audit.AuditGuardError("EXACT_FIXTURE_GUARD"), "EXACT_FIXTURE_GUARD"),
    (audit.AuditGuardError("private row must stay hidden"), "COUNT_REQUALIFICATION_GUARD_OR_OPERATION_FAILED"),
    (ValueError("PRIVATE_UPPERCASE_LIBRARY_TEXT"), "COUNT_REQUALIFICATION_GUARD_OR_OPERATION_FAILED"),
])
def test_cli_exposes_only_fixed_explicit_guard_codes(capsys, monkeypatch, error, expected):
    def fail(*args, **kwargs):
        raise error
    monkeypatch.setattr(audit, "prepare_package", fail)
    assert cli.main(["prepare", "--inventory", "fictional", "--output", "fictional"]) == 1
    output = capsys.readouterr()
    assert output.err == ""
    assert json.loads(output.out)["reason"] == expected


def test_go_template_rejected_before_any_context_or_clock_access():
    go = {name: None for name in audit.GO_KEYS}
    go.update(schema_version=audit.VERSION + "-GO", approved=False, phase="restore", repository=audit.REPO,
        plan_sha256="a" * 64, single_writer_group="nfl-lab-single-writer")
    with pytest.raises(ValueError, match="FRESH_CLOSED_PHASE_GO_REQUIRED"):
        audit.validate_go({}, "a" * 64, go, "restore", {}, ROOT)


def test_go_with_old_cutoff_rejected_before_actions_context():
    old = datetime(2026, 10, 24, 23, tzinfo=timezone.utc)
    go = {name: None for name in audit.GO_KEYS}
    go.update(schema_version=audit.VERSION + "-GO", approved=True, phase="restore", repository=audit.REPO,
        plan_sha256="a" * 64, single_writer_group="nfl-lab-single-writer", issued_at_utc=old.isoformat(),
        expires_at_utc=(old + timedelta(minutes=30)).isoformat(), maximum_new_fits=0,
        source_acquisitions=0, remote_writes=0, protected_outcome_reads=0)
    with pytest.raises(ValueError, match="FRESH_GO_CLOCK_REQUIRED"):
        audit.validate_go(dict(authority=dict(old_continuation_cutoff_utc="2026-10-25T00:00:00Z")),
            "a" * 64, go, "restore", {}, ROOT)


def test_prepare_exact_logical_scope_and_false_go_templates(tmp_path):
    registration = json.loads((ROOT / "config/weekly-initial-continuation-v6-registration.json").read_text())
    handoff = registration["parent"]["handoff"]
    runtime, descriptor = handoff["runtime_binding"], handoff["index_descriptor"]
    assets = [dict(id=runtime["canary_asset_id"], name=runtime["canary_name"], size=runtime["canary_bytes"]),
        dict(id=descriptor["manifest_asset_id"], name="manifest-" + descriptor["manifest_sha256"] + ".json", size=descriptor["manifest_bytes"]),
        dict(id=descriptor["entry"]["payload_asset_id"], name=descriptor["entry"]["payload_name"], size=descriptor["entry"]["payload"]["bytes"])]
    inventory = tmp_path / "inventory.json"
    inventory.write_text(json.dumps([dict(id=runtime["release_id"], tag_name=runtime["tag_name"], draft=True, published_at=None, assets=assets)]))
    result = audit.prepare_package(ROOT, inventory, tmp_path / "package")
    assert result["logical_files"] == 78 and result["model_pairs"] == 18
    assert result["private_body_reads"] == 0
    plan = json.loads((tmp_path / "package/PLAN.json").read_text())
    assert len(plan["logical_allowlist"]) == 78
    assert "models/rec/count_A/trained.joblib" in plan["logical_allowlist"]
    assert plan["limits"]["remote_writes"] == plan["limits"]["maximum_new_fits"] == 0
    for phase in ("restore", "requalify"):
        template = json.loads((tmp_path / ("package/GO." + phase + ".template.json")).read_text())
        assert set(template) == audit.GO_KEYS
        assert template["approved"] is False and template["rights_review"]["approved"] is False
    assert (tmp_path / "package").stat().st_mode & 0o777 == 0o700
    assert (tmp_path / "package/PLAN.json").stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize("producer_success", [True, False])
def test_get_only_wrapper_restores_real_codec_and_checks_producer(tmp_path, monkeypatch, producer_success):
    # Existing service fixture creates invented opaque bytes. Only its transport
    # and archived qualification API witness are injected; the real extractor,
    # inventory, canary checks, source receipts, hashes and CAS all execute.
    import test_gha_private_checkpoint as fixtures
    from test_private_draft_store_v2 import Response, RUN, SOURCE
    from nfl_lab import private_draft_store as core, owner_private_bootstrap as owner
    fixture = fixtures.CheckpointTests(methodName="runTest")
    fixture.setUp()
    try:
        handoff = fixture.produce()
        fixture.server.calls.clear()
        current_run, current_source = "40000000002", "b" * 40
        workflow = fixture.job["workflow_ref"]
        parent = dict(run_id=RUN, source_sha=SOURCE, handoff=handoff, producer_api_job_id=777,
            producer_job_id=fixture.config["produce_job"], workflow_ref=workflow)
        config = deepcopy(fixture.config)
        config.update(binding_sha256=core.sha(core.canonical(fixture.runtime)),
            qualification_sha256=core.sha(core.canonical(fixture.q)), canary_source_sha=fixture.q["source_sha"])
        actual = dict(binding=fixture.runtime, qualification=fixture.q, source_sha=fixture.q["source_sha"])
        original_read = audit.read_json
        def read(path, maximum=1 << 20):
            if str(path).endswith("ACTUAL_HOSTED_RESULT.json"):
                return actual
            return original_read(path, maximum)
        monkeypatch.setattr(audit, "read_json", read)
        past_checked = []
        monkeypatch.setattr(owner, "authenticate_past_run", lambda client, q: past_checked.append(q))
        root = tmp_path / "hosted"
        root.mkdir(mode=0o700)
        storage = OperationalStorage(root / "cache", fixture.policy, state=root / "state")
        storage.register_root(root)
        go = dict(output_root=str(root), source_sha=current_source, run_id=current_run,
            issued_at_utc=audit.now().isoformat(), plan_sha256="c" * 64, rights_review={"fictional": True})
        plan = dict(parent=parent, checkpoint_config=config, limits={"HTTP_calls": 360})
        job = dict(execution_lane="github_actions", workflow_ref=workflow, workflow_sha=current_source,
            job_id=audit.RESTORE_JOB, permission="write", event_name="workflow_dispatch", api_job_id=0, run_authenticated=False)
        requests = []
        def transport(request, timeout):
            requests.append(request)
            assert request.method == "GET", "recovery attempted a remote mutation"
            url = request.full_url
            if url.startswith(core.API + "/actions/runs/"):
                rid = url.split("/runs/")[1].split("/")[0]
                is_parent = rid == RUN
                if "/jobs?" in url:
                    row = dict(id=777 if is_parent else 778,
                        name=parent["producer_job_id"] if is_parent else audit.RESTORE_JOB,
                        head_sha=SOURCE if is_parent else current_source, run_id=int(rid),
                        status="completed" if is_parent else "in_progress", conclusion="success" if producer_success else "failure",
                        completed_at=(audit.now() - timedelta(seconds=1)).isoformat())
                    return Response(dict(total_count=1, jobs=[row]))
                return Response(dict(id=int(rid), head_sha=SOURCE if is_parent else current_source,
                    event="workflow_dispatch", run_attempt=1, status="completed" if is_parent else "in_progress",
                    conclusion="failure" if is_parent else None, path=".github/workflows/lab.yml",
                    repository={"full_name": core.REPO}, head_repository={"full_name": core.REPO}))
            return fixture.server(request, timeout)
        if not producer_success:
            with pytest.raises(ValueError, match="SUCCESSFUL_ORIGINAL_PRODUCER_REQUIRED"):
                audit.restore_checkpoint(plan, go, storage, job, {"GITHUB_TOKEN": "ghs_FICTIONAL"}, transport=transport)
            assert all("/releases/assets/" not in r.full_url for r in requests)
        else:
            result = audit.restore_checkpoint(plan, go, storage, job, {"GITHUB_TOKEN": "ghs_FICTIONAL"}, transport=transport)
            assert result["model_decodes"] == result["remote_writes"] == result["fits"] == 0
            assert result["state"] == "QUALIFIED_ROUTE_RESTORED_OPAQUE"
            assert result["current_run_id"] == current_run
            assert result["restorer"]["run_id"] == current_run
            assert past_checked == [fixture.q]
            restored = json.loads((root / "restore/RESTORE_FINISHED.json").read_text())
            assert restored["files"] == 78 and len(restored["models"]) == 18
            assert all(r.method == "GET" for r in requests)
    finally:
        fixture.tearDown()
