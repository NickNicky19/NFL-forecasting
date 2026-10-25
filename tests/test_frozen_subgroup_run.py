"""Fictional metadata/rows, a full-matrix storage double, and one real quota unit."""
from contextlib import contextmanager
import gzip
import hashlib
import importlib.metadata
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pytest

from nfl_lab import frozen_subgroup_run as runner
from nfl_lab.models import COUNT_TARGETS, TARGETS
from nfl_lab.operational_storage import OperationalStorage


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    body = (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()
    path.write_bytes(body)
    return {"path": str(path), "sha256": hashlib.sha256(body).hexdigest()}


def read_gzip(path):
    return json.loads(gzip.decompress(path.read_bytes()))


class FictionalStorage:
    instances = []

    def __init__(self, cache, policy):
        self.depth, self.output, self.writes, self.scans = 0, None, [], 0
        self.fail_private = False
        self.__class__.instances.append(self)

    @contextmanager
    def _locked(self):
        self.depth += 1
        try:
            yield
        finally:
            self.depth -= 1

    def _refresh(self):
        assert self.depth

    def _scan(self):
        assert self.depth
        self.scans += 1
        return {"physical_bytes": 100, "limit_bytes": 512 * 1024**2, "roots": ["FICTIONAL_PRIVATE_ROOT"]}

    def register_root(self, path):
        self.output = Path(path)
        self.output.mkdir()
        return self.output

    def write_bytes(self, path, body):
        path = Path(path)
        assert self.depth and self.output in path.parents
        assert not path.exists(), "no replacements or retries"
        if self.fail_private and "players" in path.parts:
            raise RuntimeError("fictional quota/resource stop")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
        self.writes.append(path)

    def atomic_json(self, path, value):
        self.write_bytes(path, (json.dumps(value, sort_keys=True, allow_nan=False) + "\n").encode())


def single_row(year, target, method):
    binary, count = target == "anytime_td", target in COUNT_TARGETS
    actual = np.nan if year == 2023 else 1. if binary and year == 2024 else -2. if not binary and not count and year == 2024 else -0.
    point = 0. if binary else 1.
    law = method == "leaf_cdf"
    kickoff = pd.Timestamp(f"{year}-09-15", tz="UTC")
    log = np.inf if binary and actual == 1 else .4 if np.isfinite(actual) else np.nan
    return pd.DataFrame([{"season": year, "year": year, "week": 1, "game_id": f"PRIVATE-game-{year}",
        "player_id": f"PRIVATE-player-{year}", "target": target, "method": method, "season_type": "REG",
        "point": point, "probability": point if binary else np.nan, "mean": point if law else np.nan,
        "median": point if law else np.nan, "actual": actual, "participation_state": "unknown" if year == 2023 else "played",
        "outcome_state": "unknown" if year == 2023 else "played_zero" if actual == 0 else "played_nonzero",
        "primary_role": True, "position": "QB", "team": "FIC", "opponent": "TST", "history_state": "warm",
        "fallback": "", "cutoff_utc": kickoff - pd.Timedelta(hours=1), "kickoff_utc": kickoff,
        "p10": (0. if binary or count else -3.) if law else np.nan, "p90": (1. if binary else 5.) if law else np.nan,
        "variance": (0. if binary else 2.) if law else np.nan, "crps": ((point - actual)**2 if binary else .3) if law and np.isfinite(actual) else np.nan,
        "log_score": log if law else np.nan, "cdf_actual_below": (1. if binary and actual == 1 else .1 if not binary else 0.) if law and np.isfinite(actual) else np.nan,
        "cdf_actual": (1. if binary else .7) if law and np.isfinite(actual) else np.nan,
        "UNREAD_EXTRA_COLUMN": "FICTIONAL_SOURCE_BODY_NOT_PROJECTED"}])


def prepare(tmp_path, monkeypatch, *, kind="benchmark", completed=None, retain_season_type=True):
    FictionalStorage.instances.clear()
    parent_root = tmp_path / "original"
    parent_root.mkdir()
    source = tmp_path / "cache" / "source-manifest.json"
    source_binding = write_json(source, {"fictional_metadata_only": True})
    categories = {target: {"state": "BLOCKED_LABEL_CONTRACT" if target == "fantasy_ppr" else "READY",
        "support": "bernoulli" if target == "anytime_td" else "count" if target in COUNT_TARGETS else "signed_integer",
        "primary_roles": ["QB"], "modeled_roles": ["QB"], "panels": {"base": ["f_prior"], "context": ["f_prior"]}} for target in TARGETS}
    contract = write_json(tmp_path / "categories.json", {"categories": categories})
    policy = write_json(tmp_path / "source-policy.json", {"storage": {"version": "operational-storage-v2", "limit_bytes": 512 * 1024**2},
        "namespaces": {"private_retention_bytes": 512 * 1024**2}})
    parent = write_json(tmp_path / "parent-policy.json", {"output": str(parent_root), "cache": str(source.parent),
        "source_policy": policy, "source_manifest": source_binding, "category_contract": contract})
    monkeypatch.setattr(runner, "PARENT_POLICY_SHA256", parent["sha256"])
    plan = write_json(tmp_path / "subgroup-plan.json", {"parent_policy_sha256": parent["sha256"],
        "parent_actual_freeze_sha256": runner.PARENT_EXECUTION_FREEZE_SHA256})
    monkeypatch.setattr(runner, "REGISTRATION_SHA256", plan["sha256"])
    forecast_sha = "a" * 64
    execution = parent
    if kind == "report_recovery":
        parent_root = tmp_path / "recovery"
        parent_root.mkdir()
        execution = write_json(tmp_path / "recovery-execution.json", {"parent_config": parent,
            "parent_forecast_freeze": {"path": str(tmp_path / "original/forecast-freeze.json"), "sha256": forecast_sha}, "output": str(parent_root)})
    slots, files, bindings, frames = [], [], {}, {}
    if completed is None:
        completed = {(year, target, method) for year in runner.YEARS for target in TARGETS if target != "fantasy_ppr" for method in runner.METHODS}
    for year in runner.YEARS:
        for target in TARGETS:
            for method in runner.METHODS:
                key = (year, target, method)
                slot = {"year": year, "target": target, "method": method,
                    "state": "BLOCKED" if target == "fantasy_ppr" else "COMPLETED" if key in completed else "SCORING_FAILED", "rows": 1,
                    "reason": "PRIVATE failure detail" if key not in completed else ""}
                slots.append(slot)
                if key not in completed or target == "fantasy_ppr":
                    continue
                relative = f"private/scored/{year}/{target}/{method}/rows.parquet"
                binding = write_json(parent_root / relative, {"fictional_scored_bytes": relative})
                bindings[relative] = binding["sha256"]
                files.append(relative)
                frames[str(parent_root / relative)] = single_row(year, target, method)
                if not retain_season_type:
                    frames[str(parent_root / relative)].drop(columns="season_type", inplace=True)
                if method == "leaf_cdf":
                    relative = f"private/scored/{year}/{target}/{method}/role-prior.parquet"
                    binding = write_json(parent_root / relative, {"fictional_prior_not_decoded": True})
                    bindings[relative] = binding["sha256"]
                    files.append(relative)
    manifest = {"state": "SCORED_ROWS_FROZEN", "registration_sha256": execution["sha256"],
        "parent_forecast_freeze_sha256" if kind == "report_recovery" else "forecast_freeze_sha256": forecast_sha,
        "slots": slots, "scored_files": files, "bindings": bindings, "usage": {"fictional": True}}
    manifest_binding = write_json(parent_root / "scored-freeze.json", manifest)
    root = Path(runner.__file__).resolve().parent.parent
    spec = {"registration_id": runner.VERSION, "subgroup_plan": plan, "parent_policy": parent, "parent_execution": execution,
        "parent_kind": kind, "parent_output": str(parent_root), "scored_manifest": manifest_binding,
        "forecast_freeze_sha256": forecast_sha, "source_policy": policy, "source_manifest": source_binding,
        "category_contract": contract, "cache": str(source.parent), "output": str(tmp_path / "subgroups"),
        "code_sha256": {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest() for path in (root / "nfl_lab").rglob("*.py")},
        "environment": {"python": sys.version, "executable": sys.executable, "threads": 1,
            "packages": {name: importlib.metadata.version(name) for name in runner.PACKAGES}}, "budgets": runner.LIMITS.copy()}
    config = write_json(tmp_path / "execution.json", spec)
    batches, reads = [], []
    def validate(storage, expected):
        assert storage.depth
        for path, digest in expected.items():
            assert hashlib.sha256(Path(path).read_bytes()).hexdigest() == digest
        batches.append(dict(expected))
        return {}, {"fictional_owned_validation": True, "full_scan_calls": 2}
    def read(path, *, columns, filters):
        path = str(path)
        assert (Path(spec["output"]) / "SUBGROUPS_CONSUMED.json").exists()
        assert path in frames and "role-prior" not in path
        has_type = "season_type" in frames[path]
        assert columns == [name for name in runner.READ_COLUMNS if name != "season_type" or has_type]
        assert "UNREAD_EXTRA_COLUMN" not in columns
        year = int(Path(path).parts[-4])
        assert filters == [("season", "==", year), ("year", "==", year)] + ([("season_type", "==", "REG")] if has_type else [])
        reads.append(path)
        frame = frames[path]
        mask = frame.season.eq(year) & frame.year.eq(year)
        if has_type:
            mask &= frame.season_type.eq("REG")
        return frame.loc[mask, columns].copy()
    monkeypatch.setattr(runner, "OperationalStorage", FictionalStorage)
    monkeypatch.setattr(runner, "validate_owned_references", validate)
    monkeypatch.setattr(runner, "_schema_columns", lambda path: set(frames[str(path)].columns))
    monkeypatch.setattr(pd, "read_parquet", read)
    return config, spec, manifest, frames, batches, reads


def test_full_72_matrix_streams_private_gzip_and_retains_all_parent_statuses(tmp_path, monkeypatch):
    config, spec, manifest, frames, batches, reads = prepare(tmp_path, monkeypatch, retain_season_type=False)
    before = {path: frame.copy(deep=True) for path, frame in frames.items()}
    original = runner.build_frozen_subgroups
    observed = []
    def checked(rows, category):
        assert rows.target.nunique() == rows.method.nunique() == 1 and len(rows) == 3
        assert rows.primary_role.dtype == bool and rows.actual.dtype == np.dtype("float64")
        assert "season_type" not in rows
        assert np.signbit(rows.loc[rows.season.eq(2022), "actual"]).all()
        assert rows.loc[rows.season.eq(2023), "actual"].isna().all()
        observed.append((category["target"], rows.method.iloc[0]))
        return original(rows, category)
    monkeypatch.setattr(runner, "build_frozen_subgroups", checked)
    result = runner.run_subgroups(config["path"], config["sha256"])
    output = Path(spec["output"])
    assert len(result["annual_slots"]) == 216 and len(result["pooled_slots"]) == 72
    assert sum(s["state"] == "BLOCKED_EXACT_PPR" for s in result["pooled_slots"]) == 6
    assert sum(s["state"] == "COMPLETED" for s in result["pooled_slots"]) == 66
    assert len(observed) == 66 and len(reads) == 198 and len(batches) == 3
    assert all("absent;" in value for slot in result["pooled_slots"] for value in slot.get("season_type_metadata", {}).values())
    assert set(batches[1]) == set(str(Path(spec["parent_output"]) / name) for name in manifest["scored_files"]) | {spec["scored_manifest"]["path"], spec["source_manifest"]["path"]}
    assert len(list((output / "private/players").rglob("*.json.gz"))) == 66
    assert len(list((output / "public/groups").rglob("*.json.gz"))) == 66
    for path in (output / "public").rglob("*.json.gz"):
        text = gzip.decompress(path.read_bytes()).decode()
        assert "PRIVATE-player" not in text and "PRIVATE-game" not in text and "PRIVATE failure" not in text
        assert '"private":' not in text
        json.loads(text, parse_constant=lambda x: pytest.fail("nonfinite JSON"))
    private = read_gzip(output / "private/players/anytime_td/leaf_cdf.json.gz")
    assert "PRIVATE-player" in json.dumps(private)
    binary = read_gzip(output / "public/groups/anytime_td/leaf_cdf.json.gz")
    assert binary["populations"]["all_offered"]["summary"]["log_loss_state"] == "positive_infinity"
    assert json.loads((output / "SUBGROUPS_FINISHED.json").read_text())["state"] == "COMPLETED"
    assert not list((output / "private/players").rglob("*.json"))
    for path in before:
        pd.testing.assert_frame_equal(frames[path], before[path], check_exact=True)
    with pytest.raises(RuntimeError, match="cannot retry"):
        runner.run_subgroups(config["path"], config["sha256"])


def test_recovery_schema_partial_and_failed_cells_keep_statuses(tmp_path, monkeypatch):
    completed = {(2022, "pass_yd", "leaf_cdf")}
    config, spec, _, _, _, reads = prepare(tmp_path, monkeypatch, kind="report_recovery", completed=completed)
    result = runner.run_subgroups(config["path"], config["sha256"])
    slot = next(s for s in result["pooled_slots"] if s["target"] == "pass_yd" and s["method"] == "leaf_cdf")
    assert slot["state"] == "PARTIAL_COMPLETED_YEARS" and slot["included_years"] == [2022]
    assert slot["absent_years"] == [2023, 2024] and len(reads) == 1
    assert slot["season_type_metadata"] == {"2022": "present_validated_REG"}
    assert sum(s["state"] == "SCORING_FAILED" for s in result["annual_slots"]) == 197
    assert sum(s["state"] == "MISSING_OR_UNRUN" for s in result["pooled_slots"]) == 65


@pytest.mark.parametrize("damage", ["protected_year", "duplicate_file", "unsafe_binding", "missing_row_binding", "completed_missing_file", "unblocked_ppr", "duplicate_slot", "wrong_parent_forecast"])
def test_manifest_rejection_precedes_any_scored_row_read(tmp_path, monkeypatch, damage):
    config, spec, manifest, _, _, reads = prepare(tmp_path, monkeypatch, completed={(2022, "pass_yd", "recent")})
    if damage == "protected_year":
        manifest["slots"][0]["year"] = 2025
    elif damage == "duplicate_file":
        manifest["scored_files"] *= 2
    elif damage == "unsafe_binding":
        manifest["bindings"]["../escape"] = "a" * 64
    elif damage == "missing_row_binding":
        manifest["bindings"].clear()
    elif damage == "completed_missing_file":
        manifest["scored_files"].clear()
    elif damage == "unblocked_ppr":
        next(s for s in manifest["slots"] if s["target"] == "fantasy_ppr")["state"] = "COMPLETED"
    elif damage == "duplicate_slot":
        manifest["slots"][-1] = manifest["slots"][0]
    else:
        manifest["forecast_freeze_sha256"] = "b" * 64
    spec["scored_manifest"] = write_json(Path(spec["scored_manifest"]["path"]), manifest)
    config = write_json(Path(config["path"]), spec)
    with pytest.raises(ValueError):
        runner.run_subgroups(config["path"], config["sha256"])
    assert reads == []
    output = Path(spec["output"])
    assert (output / "SUBGROUPS_CONSUMED.json").exists()
    assert json.loads((output / "SUBGROUPS_FINISHED.json").read_text())["state"] == "FAILED"


@pytest.mark.parametrize("damage", ["config_hash", "code", "source_pointer", "new_budget", "parent_output", "environment"])
def test_preflight_rejects_changed_frozen_inputs_without_consuming_rows(tmp_path, monkeypatch, damage):
    config, spec, _, _, _, reads = prepare(tmp_path, monkeypatch, completed=set())
    if damage == "code":
        spec["code_sha256"][next(iter(spec["code_sha256"]))] = "0" * 64
    elif damage == "source_pointer":
        spec["source_manifest"]["sha256"] = "0" * 64
    elif damage == "new_budget":
        spec["budgets"]["max_wall_seconds"] += 1
    elif damage == "parent_output":
        spec["output"] = spec["parent_output"]
    elif damage == "environment":
        spec["environment"]["threads"] = 2
    config = write_json(Path(config["path"]), spec)
    with pytest.raises(ValueError):
        runner.run_subgroups(config["path"], "0" * 64 if damage == "config_hash" else config["sha256"])
    assert not reads and not (Path(spec["output"]) / "SUBGROUPS_CONSUMED.json").exists()


def test_failure_preserves_consumption_partial_files_and_stops_without_retry(tmp_path, monkeypatch):
    config, spec, _, _, _, reads = prepare(tmp_path, monkeypatch, completed={(2022, "pass_yd", "recent")})
    original = FictionalStorage.register_root
    def inject(self, path):
        result = original(self, path)
        self.fail_private = True
        return result
    monkeypatch.setattr(FictionalStorage, "register_root", inject)
    with pytest.raises(RuntimeError, match="resource stop"):
        runner.run_subgroups(config["path"], config["sha256"])
    output = Path(spec["output"])
    assert len(reads) == 1 and (output / "public/groups/pass_yd/recent.json.gz").exists()
    assert (output / "SUBGROUPS_FAILURE.json").exists() and not (output / "public/report.json.gz").exists()
    with pytest.raises(RuntimeError, match="cannot retry"):
        runner.run_subgroups(config["path"], config["sha256"])


@pytest.mark.parametrize("field,value", [("season", 2025), ("year", 2024), ("season_type", "POST"), ("target", "pass_att"), ("method", "pooled")])
def test_annual_projection_filters_and_cell_guards_reject_changed_rows(tmp_path, monkeypatch, field, value):
    config, spec, _, frames, _, _ = prepare(tmp_path, monkeypatch, completed={(2022, "pass_yd", "recent")})
    next(iter(frames.values())).loc[0, field] = value
    with pytest.raises(ValueError, match="annual identity/type"):
        runner.run_subgroups(config["path"], config["sha256"])
    assert not list((Path(spec["output"]) / "public/groups").rglob("*.gz"))


def test_real_quota_gzip_is_deterministic_owned_and_only_compressed(tmp_path):
    policy = {"storage": {"version": "operational-storage-v2", "limit_bytes": 65536}, "namespaces": {"private_retention_bytes": 65536}}
    storage = OperationalStorage(tmp_path / "cache", policy)
    value = {"fictional_private_player_groups": [{"player_id": "FICTIONAL-PRIVATE", "metric": 1.25}] * 200}
    first, second = storage.feature_root / "first.json.gz", storage.feature_root / "second.json.gz"
    a, b = runner._write_gzip(storage, first, value), runner._write_gzip(storage, second, value)
    assert a == b and first.read_bytes() == second.read_bytes()
    assert first.read_bytes()[4:8] == b"\0\0\0\0"
    assert read_gzip(first) == value and a["bytes"] < len(json.dumps(value))
    assert first.stat().st_ino == second.stat().st_ino
    assert storage.validate_reference(first, a["sha256"])["bytes"] == a["bytes"]
    assert not list(storage.feature_root.glob("*.json"))


def test_mixed_optional_season_metadata_is_validated_without_synthesizing_cells(tmp_path, monkeypatch):
    completed = {(year, "pass_yd", "recent") for year in runner.YEARS}
    config, spec, _, frames, _, _ = prepare(tmp_path, monkeypatch, completed=completed)
    frames[next(path for path in frames if "/2023/" in path)].drop(columns="season_type", inplace=True)
    original = runner.build_frozen_subgroups
    def checked(rows, category):
        assert "season_type" not in rows
        return original(rows, category)
    monkeypatch.setattr(runner, "build_frozen_subgroups", checked)
    result = runner.run_subgroups(config["path"], config["sha256"])
    slot = next(s for s in result["pooled_slots"] if s["target"] == "pass_yd" and s["method"] == "recent")
    assert slot["season_type_metadata"]["2022"] == slot["season_type_metadata"]["2024"] == "present_validated_REG"
    assert slot["season_type_metadata"]["2023"].startswith("absent;")
