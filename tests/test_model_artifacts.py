"""Frozen inference parity and local consumer failure/rollback contracts."""
from hashlib import sha256
import json

import numpy as np
import pandas as pd
import pytest

from nfl_lab.model_artifacts import (
    ArtifactError, activate_artifact, load_artifact, predict_active_artifact,
    predict_artifact, rollback_artifact, main,
)
from nfl_lab.models import METHODS, fit_predict
from test_models import histories


QUALIFIED = {"source_qualified": True, "availability_verified": True, "input_sha256": "b" * 64}


def parity(expected, actual):
    # sklearn's parallel tree summation and BLAS dot order can differ at the
    # last floating-point bits. Distribution/point/fallback semantics must match.
    pd.testing.assert_frame_equal(expected, actual, check_exact=False, rtol=1e-12, atol=1e-12)


@pytest.mark.parametrize("method", METHODS)
def test_export_default_parity_and_replay_all_registered_methods(tmp_path, method):
    train, test = histories()
    path = tmp_path / f"{method}.json"
    expected = fit_predict(train, test, "pass_yd", method)
    exported = fit_predict(train, test, "pass_yd", method, artifact_path=path)
    pd.testing.assert_frame_equal(expected, exported)
    assert expected.attrs.keys() == exported.attrs.keys()
    for key in ("model_version", "target", "method", "seed", "fallback_rows", "abstention_rows"):
        assert expected.attrs[key] == exported.attrs[key]
    loaded = load_artifact(path)
    assert loaded["artifact"]["contains_raw_training_rows"] is False
    assert "game-0" not in path.read_text()
    assert loaded["artifact"]["environment"]["requirements_lock"]
    replayed = predict_artifact(path, test, input_manifest=QUALIFIED)
    parity(expected, replayed)
    assert replayed.attrs["replay_mode"] == "frozen parameters; no training rows or refit"
    with pytest.raises(FileExistsError):
        fit_predict(train, test, "pass_yd", method, artifact_path=path)


@pytest.mark.parametrize("target,method", [
    ("pass_td", "distributional"), ("pass_att", "ridge"),
    ("pass_cmp", "ensemble"), ("rush_att", "workload"),
    ("rec_yd", "workload"), ("rush_rec_yd", "workload"),
    ("anytime_td", "ridge"), ("anytime_td", "tree"),
    ("anytime_td", "distributional"),
])
def test_count_binary_and_workload_replay(tmp_path, target, method):
    train, test = histories()
    path = tmp_path / "model.json"
    expected = fit_predict(train, test, target, method, artifact_path=path)
    parity(expected, predict_artifact(path, test, input_manifest=QUALIFIED))


def test_full_learned_tree_is_saved_and_replay_never_calls_fit(tmp_path, monkeypatch):
    from sklearn.ensemble import ExtraTreesRegressor
    train, test = histories(400)
    path = tmp_path / "tree.json"
    expected = fit_predict(train, test, "pass_yd", "tree", artifact_path=path)
    state = load_artifact(path)["artifact"]["inference"]["estimator"]
    assert len(state["trees"]) == 24
    assert any(len(tree["left"]) > 1 for tree in state["trees"])
    def forbidden_fit(*args, **kwargs):
        raise AssertionError("replay must not fit")
    monkeypatch.setattr(ExtraTreesRegressor, "fit", forbidden_fit)
    parity(expected, predict_artifact(path, test, input_manifest=QUALIFIED))
    with pytest.raises(FileExistsError):
        fit_predict(train, test, "pass_yd", "tree", artifact_path=path)


def test_all_missing_features_replay_prior_fallback(tmp_path):
    train, test = histories()
    for name in test:
        if name.startswith("f_"):
            test[name] = np.nan
    path = tmp_path / "missing.json"
    expected = fit_predict(train, test, "pass_att", "ridge", artifact_path=path)
    assert expected.fallback.str.startswith("all_numeric_features_missing:").all()
    parity(expected, predict_artifact(path, test, input_manifest=QUALIFIED))


@pytest.mark.parametrize("case", ["insufficient", "single_class", "no_outcomes", "fit_failed"])
def test_unfitted_states_export_explicit_fallback_without_weights(tmp_path, case, monkeypatch):
    from sklearn.linear_model import Ridge
    train, test = histories()
    target = "pass_att"
    if case == "insufficient":
        train = train.iloc[:10]
    elif case == "single_class":
        target = "anytime_td"
        train[target] = 0
    elif case == "no_outcomes":
        target = "fantasy_ppr"
        train[target] = np.nan
    else:
        def numerical_failure(*args, **kwargs):
            raise ValueError("injected numerical failure")
        monkeypatch.setattr(Ridge, "fit", numerical_failure)
    path = tmp_path / "fallback.json"
    expected = fit_predict(train, test, target, "ridge", artifact_path=path)
    state = load_artifact(path)["artifact"]["inference"]
    assert "estimator" not in state
    assert "coefficient" not in state
    assert "trees" not in state
    parity(expected, predict_artifact(path, test, input_manifest=QUALIFIED))


@pytest.mark.parametrize("failure", ["missing", "text", "infinite", "late_cutoff", "unqualified", "no_hash"])
def test_source_schema_and_qualification_fail_closed(tmp_path, failure):
    train, test = histories()
    path = tmp_path / "schema.json"
    fit_predict(train, test, "pass_att", "ridge", artifact_path=path)
    manifest = QUALIFIED.copy()
    if failure == "missing":
        test = test.drop(columns="f_player_pass_att_mean3")
    elif failure == "text":
        test["f_player_pass_att_mean3"] = "twenty"
    elif failure == "infinite":
        test["f_player_pass_att_mean3"] = np.inf
    elif failure == "late_cutoff":
        test["cutoff_utc"] = test["kickoff_utc"] + pd.Timedelta(seconds=1)
    elif failure == "unqualified":
        manifest["availability_verified"] = False
    else:
        manifest["input_sha256"] = ""
    with pytest.raises(ArtifactError):
        predict_artifact(path, test, input_manifest=manifest)


def test_missing_legacy_history_columns_do_not_export_an_invented_model(tmp_path):
    train, test = histories()
    test = test.drop(columns=["f_player_pass_att_mean3", "f_player_pass_att_n3"])
    path = tmp_path / "legacy.json"
    fit_predict(train, test, "pass_att", "recent", artifact_path=path)
    payload = json.loads(path.read_text())["artifact"]
    assert payload["replayable"] is False
    with pytest.raises(ArtifactError, match="legacy training-history"):
        predict_artifact(path, test, input_manifest=QUALIFIED)


def test_restart_and_local_rollback_restore_exact_prior_artifact(tmp_path):
    train, test = histories()
    old, new, pointer = tmp_path / "old.json", tmp_path / "new.json", tmp_path / "active.json"
    old_predictions = fit_predict(train, test, "pass_yd", "recent", artifact_path=old)
    new_predictions = fit_predict(train, test, "pass_yd", "ridge", artifact_path=new)
    activate_artifact(pointer, old)
    activate_artifact(pointer, new)
    parity(new_predictions, predict_active_artifact(pointer, test, input_manifest=QUALIFIED))
    rollback_artifact(pointer)
    parity(old_predictions, predict_active_artifact(pointer, test, input_manifest=QUALIFIED))
    # A new read of disk state represents process restart; no Python object is
    # retained from fit or pointer activation.
    parity(old_predictions, predict_active_artifact(str(pointer), test.copy(), input_manifest=QUALIFIED))


def test_checksum_code_and_environment_changes_block_replay(tmp_path):
    train, test = histories()
    original = tmp_path / "original.json"
    fit_predict(train, test, "pass_att", "ridge", artifact_path=original)
    wrapper = json.loads(original.read_text())
    for field in ("checksum", "code", "environment"):
        changed = json.loads(original.read_text())
        if field == "checksum":
            changed["artifact"]["target"] = "pass_td"
        elif field == "code":
            changed["artifact"]["code_sha256"]["models.py"] = "0" * 64
        else:
            changed["artifact"]["environment"]["python"] = "0.0.0"
        if field != "checksum":
            changed["sha256"] = sha256(json.dumps(changed["artifact"], sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
        path = tmp_path / f"{field}.json"
        path.write_text(json.dumps(changed))
        with pytest.raises(ArtifactError):
            predict_artifact(path, test, input_manifest=QUALIFIED)
    assert load_artifact(original)["sha256"] == wrapper["sha256"]


def test_consumer_cli_replays_frozen_artifact_after_input_roundtrip(tmp_path):
    train, test = histories()
    artifact, features, manifest, output = (tmp_path / name for name in ("ridge.json", "features.parquet", "manifest.json", "predictions.json"))
    expected = fit_predict(train, test, "pass_att", "ridge", artifact_path=artifact)
    test.to_parquet(features)
    manifest.write_text(json.dumps(QUALIFIED))
    assert main([str(artifact), str(features), str(manifest), str(output)]) == 0
    rows = pd.DataFrame(json.loads(output.read_text())["predictions"])
    np.testing.assert_allclose(rows["mean"], expected["mean"], atol=1e-9)
    assert list(rows["index"]) == list(test.index)
    with pytest.raises(FileExistsError):
        main([str(artifact), str(features), str(manifest), str(output)])


def test_failed_rollback_preserves_current_pointer(tmp_path):
    train, test = histories()
    old, new, pointer = tmp_path / "old.json", tmp_path / "new.json", tmp_path / "active.json"
    fit_predict(train, test, "pass_att", "recent", artifact_path=old)
    expected = fit_predict(train, test, "pass_att", "ridge", artifact_path=new)
    activate_artifact(pointer, old)
    activate_artifact(pointer, new)
    previous = pointer.read_bytes()
    old.write_text("{}")
    with pytest.raises(ArtifactError):
        rollback_artifact(pointer)
    assert pointer.read_bytes() == previous
    parity(expected, predict_active_artifact(pointer, test, input_manifest=QUALIFIED))


def test_corrupt_tree_edges_fail_before_inference(tmp_path):
    train, test = histories(400)
    artifact = tmp_path / "tree.json"
    fit_predict(train, test, "pass_att", "tree", artifact_path=artifact)
    wrapper = json.loads(artifact.read_text())
    tree = wrapper["artifact"]["inference"]["estimator"]["trees"][0]
    tree["left"][0] = 0
    wrapper["sha256"] = sha256(json.dumps(wrapper["artifact"], sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
    artifact.write_text(json.dumps(wrapper))
    with pytest.raises(ArtifactError, match="tree edge"):
        predict_artifact(artifact, test, input_manifest=QUALIFIED)
