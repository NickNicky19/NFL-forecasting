"""Fictional runtime plumbing and exact quota checks; no NFL evidence."""
import hashlib
import json
from pathlib import Path
import types

import numpy as np
import pandas as pd
import pytest

from nfl_lab import operational_models, operational_sources, reference_runtime as runtime
from nfl_lab.model_artifacts import ArtifactError, load_artifact, predict_artifact
from nfl_lab.models import TARGETS
from nfl_lab.operational_storage import OperationalStorage, StorageQuotaError
from nfl_lab.state import digest
from test_models import histories


def policy():
    return {"storage": {"version": "operational-storage-v2", "limit_bytes": 32 * 1024 * 1024},
            "namespaces": {"private_retention_bytes": 32 * 1024 * 1024}, "_policy_sha256": "a" * 64}


def test_state_exact_peak_and_same_byte_idempotency(tmp_path):
    state = tmp_path / "state"
    base = OperationalStorage(tmp_path / "cache", policy(), state=state)
    guarded = runtime.StateBoundStorage(base, state, limit=1000)
    overhead = sum(p.stat().st_size for p in state.rglob("*") if p.is_file())
    guarded.limit = overhead + 4
    guarded.write_bytes(state / "provisional.json", b"1234")
    guarded.write_bytes(state / "provisional.json", b"1234")
    with pytest.raises(StorageQuotaError):
        guarded.write_bytes(state / "final.json", b"1")
    assert not (state / "final.json").exists()
    assert (state / "provisional.json").read_bytes() == b"1234"


def test_state_atomic_json_exact_serialized_bytes(tmp_path):
    state = tmp_path / "state"
    base = OperationalStorage(tmp_path / "cache", policy(), state=state)
    guarded = runtime.StateBoundStorage(base, state, limit=1000)
    overhead = sum(p.stat().st_size for p in state.rglob("*") if p.is_file())
    value = {"fictional": "é"}
    guarded.limit = overhead + len(runtime._json(value)) - 1
    with pytest.raises(StorageQuotaError):
        guarded.atomic_json(state / "model.json", value)
    assert not (state / "model.json").exists()


def test_comparator_rejects_every_column_and_unavailable_participation():
    base = pd.DataFrame({"mean": [1.], "scale": [2.], "family": ["normal"], "p10": [-1.],
        "p50": [1.], "p90": [3.], "p_participation": [np.nan], "fallback": [""]})
    runtime._same(base, base.copy())
    for column in runtime.COLUMNS:
        changed = base.copy()
        changed[column] = "different" if column in ("family", "fallback") else 88.
        with pytest.raises(ValueError):
            runtime._same(base, changed)


def test_end_to_end_fictional_all_packages_consumed_once(tmp_path, monkeypatch):
    """Contract and fresh transport are stubbed here; integrated suites own them."""
    train, query = histories(40)
    train["outcome_available_utc"] = train.kickoff_utc + pd.Timedelta(days=7)
    cutoff = pd.Timestamp("2025-01-01T00:00:00Z")
    query = query.reset_index(drop=True)
    query["kickoff_utc"] = cutoff + pd.Timedelta(days=1)
    query["cutoff_utc"] = cutoff
    query["participation_state"] = "unknown"
    query[list(TARGETS)] = np.nan
    train.to_parquet(tmp_path / "train.parquet")
    query.to_parquet(tmp_path / "query.parquet")
    for name, value in (("source.json", {}), ("accepted.json", {}), ("metadata.json", {}), ("policy.json", {})):
        (tmp_path / name).write_text(json.dumps(value))
    def spec(path):
        return {"path": str(path), "sha256": runtime._sha(path), "bytes": path.stat().st_size}
    source = {"adapter_version": operational_sources.VERSION, "policy_sha256": "a" * 64,
        "snapshot_sha256": "b" * 64, "training_view_sha256": "c" * 64, "namespace": "fictional"}
    fake_policy = policy()
    fake_policy["_policy_sha256"] = runtime._sha(tmp_path / "policy.json")
    source["policy_sha256"] = fake_policy["_policy_sha256"]
    monkeypatch.setattr(operational_sources, "load_source_policy", lambda p: fake_policy)
    monkeypatch.setattr(operational_sources, "_verify", lambda *a, **k: {**source, "manifest_sha256": runtime._sha(tmp_path / "source.json")})
    (tmp_path / "source.json").write_text(json.dumps(source))
    def review(path, *, target=None, method=None, binding=None):
        wrapper = load_artifact(path)
        artifact = wrapper["artifact"]
        if not isinstance(artifact["inference"]["global_prior"]["mean"], (float, int)):
            raise ArtifactError("fictional nonnumeric prior")
        if target != artifact["target"] or method != artifact["method"] or binding != artifact["operational_source_binding"]:
            raise ArtifactError("fictional identity mismatch")
        return {"file_sha256": runtime._sha(path), "artifact_sha256": wrapper["sha256"]}
    fake = types.ModuleType("nfl_lab.reference_contract")
    fake.review_reference_artifact = review
    fake.independent_reference = lambda path, q: predict_artifact(path, q, input_manifest={"source_qualified": True,
        "availability_verified": True, "input_sha256": "d" * 64})
    monkeypatch.setitem(__import__("sys").modules, "nfl_lab.reference_contract", fake)
    # The runtime records the real module hash; supply a fictional existing code
    # file in this isolated test without importing or editing another module.
    original_sha = runtime._sha
    monkeypatch.setattr(runtime, "_sha", lambda p: "e" * 64 if Path(p).name == "reference_contract.py" and not Path(p).exists() else original_sha(p))
    def fresh(context, storage, output, budget):
        ctx = json.loads(context.read_text())
        result = []
        for p in ctx["packages"]:
            frame = pd.read_parquet(p["prediction_path"])
            clean = frame.astype(object).where(frame.notna(), None)
            result.append({"target": p["target"], "method": p["method"], "columns": list(frame),
                "index": frame.index.tolist(), "rows": clean.values.tolist()})
        return result
    monkeypatch.setattr(runtime, "_fresh", fresh)
    config = {"registration_id": runtime.REGISTRATION, "targets": list(TARGETS), "methods": ["recent", "pooled"],
        "blocked": {"fantasy_ppr": "blocked fictional"}, "source_policy": spec(tmp_path / "policy.json"),
        "inputs": {"training_features": spec(tmp_path / "train.parquet"), "query_features": spec(tmp_path / "query.parquet"),
            "source_manifest": spec(tmp_path / "source.json"), "accepted_summary": spec(tmp_path / "accepted.json"),
            "query_metadata": spec(tmp_path / "metadata.json")}, "cache": str(tmp_path / "cache"),
        "state": str(tmp_path / "state"), "output": str(tmp_path / "out"), "asof_utc": cutoff.isoformat(),
        "expected": {"training_rows": len(train), "query_rows": len(query), "query_games": query.game_id.nunique(),
            "feature_columns": sum(c.startswith("f_") for c in query), "source_snapshot_sha256": "b" * 64},
        "budgets": {"max_state_logical_bytes": 200 * 1024 * 1024, "threads": 2, "max_wall_seconds": 180,
            "reporting_reserve_seconds": 10, "max_CPU_seconds": 300, "max_RSS_bytes": 2 * 1024**3,
            "max_model_prediction_row_incidences": 100000, "max_reference_parameter_fits": 22,
            "max_package_wall_seconds": 30, "max_package_CPU_seconds": 45, "fresh_stdout_max_bytes": 1024**2}}
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(config))
    result = runtime.run_acceptance(config_path, config_sha256=runtime._sha(config_path))
    assert result["package_count"] == 22
    assert result["blocked_slots"] == 2
    assert result["usage"]["reference_parameter_fits"] == 22
    assert result["usage"]["query_forecast_route_budget_charges"] == len(query) * (22 * 5 + 5)
    assert result["usage"]["successfully_returned_query_row_incidences"] == len(query) * (22 * 5 + 1)
    assert len(result["negative_checks"]) == 4
    assert not (tmp_path / "state" / "forecasts").exists()
    with pytest.raises(RuntimeError, match="already consumed"):
        runtime.run_acceptance(config_path, config_sha256=runtime._sha(config_path))


def test_fresh_child_real_subprocess_only_saved_query_and_artifact(tmp_path):
    """Runs after integration with the strict contract; no source/training read."""
    pytest.importorskip("nfl_lab.reference_contract")
    import subprocess
    import sys
    train, query = histories(40)
    train["outcome_available_utc"] = train.kickoff_utc + pd.Timedelta(days=7)
    query = query.reset_index(drop=True)
    query["cutoff_utc"] = query.kickoff_utc.min()
    query["participation_state"] = "unknown"
    query[list(TARGETS)] = np.nan
    selected_policy = policy()
    base = OperationalStorage(tmp_path / "cache", selected_policy, state=tmp_path / "state")
    output = base.register_root(tmp_path / "output")
    manifest = {"adapter_version": operational_sources.VERSION, "policy_sha256": "a" * 64,
        "snapshot_sha256": "b" * 64, "training_view_sha256": "c" * 64, "namespace": "fictional"}
    binding = operational_models.model_binding(selected_policy, manifest, train, query, "d" * 64)
    artifact = tmp_path / "state" / "model.json"
    expected = operational_models.fit_operational_reference(train, query, "pass_yd", "recent",
        artifact_path=artifact, binding=binding, storage=runtime.StateBoundStorage(base, tmp_path / "state"))
    query.attrs.clear()
    query_path = output / "query.parquet"
    base.write_dataframe(query, query_path, index=True)
    training = tmp_path / "forbidden-training.parquet"
    train.to_parquet(training)
    context = {"query_path": str(query_path), "query_file_sha256": runtime._sha(query_path), "binding": binding,
        "packages": [{"target": "pass_yd", "method": "recent", "artifact_path": str(artifact),
            "artifact_file_sha256": runtime._sha(artifact)}], "forbidden_roots": [str(training)],
        "max_package_wall_seconds": 30, "max_package_CPU_seconds": 45}
    context_path = output / "context.json"
    base.atomic_json(context_path, context)
    class Budget:
        budgets = {"fresh_stdout_max_bytes": 1024**2}
        def check(self):
            pass
    records = runtime._fresh(context_path, base, output, Budget())
    assert len(records) == 1
    actual = pd.DataFrame(records[0]["rows"], columns=records[0]["columns"], index=records[0]["index"])
    runtime._same(expected, actual)
    # Unrelated workspace data remains denied even though it is outside every
    # protected root. Inject the read at a real guarded inference callsite.
    import tempfile
    probe = ("from pathlib import Path; import sys; "
        "from nfl_lab import reference_runtime as r, operational_models as op; "
        "original=op.frame_hash; "
        "op.frame_hash=lambda q: (Path(sys.argv[2]).read_text(), original(q))[1]; "
        "r._fresh_child(sys.argv[1])")
    with tempfile.TemporaryDirectory(prefix=".fictional-read-guard-", dir=Path(__file__).resolve().parents[1]) as directory:
        unrelated = Path(directory) / "outcomes.json"
        unrelated.write_text('{"fictional": true}')
        (Path(directory) / "traversal").mkdir()
        for attempted in (unrelated, Path(directory) / "traversal" / ".." / unrelated.name):
            denied = subprocess.run([sys.executable, "-B", "-c", probe, str(context_path), str(attempted)],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
            assert denied.returncode != 0
            assert b"outside exact data and trusted runtime allowlist" in denied.stderr
    dns_probe = ("import sys,socket; from nfl_lab import reference_runtime as r, operational_models as op; "
        "original=op.frame_hash; "
        "op.frame_hash=lambda q: (socket.getaddrinfo('fictional.invalid',80),original(q))[1]; "
        "r._fresh_child(sys.argv[1])")
    denied = subprocess.run([sys.executable, "-B", "-c", dns_probe, str(context_path)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
    assert denied.returncode != 0
    assert b"network access is forbidden" in denied.stderr
    # A forbidden training path used as query is rejected by the child audit.
    context["query_path"] = str(training.parent / "nonexistent" / ".." / training.name)
    context["query_file_sha256"] = runtime._sha(training)
    second_context = output / "forbidden-context.json"
    base.atomic_json(second_context, context)
    completed = subprocess.run([sys.executable, "-B", "-m", "nfl_lab.reference_runtime", "--fresh-context", str(second_context)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
    assert completed.returncode != 0
    assert b"cannot read source or training values" in completed.stderr


def test_distribution_output_invariants_allow_signed_yards_and_reject_bad_counts():
    frame = pd.DataFrame({"mean": [-2.], "scale": [1.], "family": ["normal"], "p10": [-3.],
        "p50": [-2.], "p90": [-1.], "p_participation": [np.nan], "fallback": [""]})
    runtime._validate_output(frame, "rush_yd")
    with pytest.raises(ValueError, match="count"):
        runtime._validate_output(frame, "pass_td")
    frame[["mean", "scale", "p10", "p50", "p90"]] = [2., 1., 0., 2., 4.]
    with pytest.raises(ValueError, match="variance"):
        runtime._validate_output(frame, "pass_td")
    frame[["mean", "scale", "p10", "p50", "p90"]] = [.5, .5, 0., 0., 1.]
    runtime._validate_output(frame, "anytime_td")
    frame["p90"] = .9
    with pytest.raises(ValueError, match="Bernoulli"):
        runtime._validate_output(frame, "anytime_td")


def test_fresh_pipe_cap_is_enforced_while_draining(tmp_path, monkeypatch):
    import subprocess
    import sys
    base = OperationalStorage(tmp_path / "cache", policy(), state=tmp_path / "state")
    output = base.register_root(tmp_path / "output")
    original = subprocess.Popen
    def noisy(args, **kwargs):
        return original([sys.executable, "-c", "import sys; sys.stdout.write('x' * 4096); sys.stdout.flush()"], **kwargs)
    monkeypatch.setattr(runtime.subprocess, "Popen", noisy)
    class Budget:
        budgets = {"fresh_stdout_max_bytes": 32}
        def check(self):
            pass
    with pytest.raises(RuntimeError, match="byte cap"):
        runtime._fresh(output / "unused-context.json", base, output, Budget())
    assert base.snapshot()["physical_bytes"] < base.limit_bytes
