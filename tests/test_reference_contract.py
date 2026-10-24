"""Fictional aggregate artifacts only: no NFL files, labels, fitting or HTTP."""
from copy import deepcopy
from hashlib import sha256
import json

import numpy as np
import pandas as pd
import pytest

from nfl_lab import reference_contract as c
from nfl_lab.model_artifacts import ArtifactError, _code_hashes, _environment, predict_artifact
from nfl_lab.models import METHODS, MODEL_VERSION, RIDGE_ALPHA, SEED, TARGETS
from nfl_lab.operational_models import PARTICIPATION, VERSION, code_hashes


def fictional(target="pass_yd", method="recent", dispersion=4.):
    window = 3 if method == "recent" else 8
    summary = [f"f_player_{target}_mean{window}", f"f_player_{target}_n{window}"]
    prior = {"mean": .25 if target == "anytime_td" else 2., "variance": 1., "n": 4}
    node = {"kind": "recent", "target": target, "window": window, "global_prior": prior,
            "position_priors": {"QB": prior.copy()}, "required_summary_columns": summary,
            "qualified_summary_columns_present": True}
    dist = None if target == "anytime_td" else {
        "dispersion_kind": "NB2_alpha" if target in c.COUNT_TARGETS else "normal_residual_variance",
        "global_dispersion": dispersion, "position_dispersion": {"QB": dispersion},
        "fit_population": "training fitted residuals; calibration not established"}
    audit = {**c.AUDIT_TEXT, "model_version": MODEL_VERSION, "target": target, "method": method, "seed": SEED,
             "temporal_training": {"input_rows": 6, "removed_future_or_unknown_time_rows": 1,
                                   "label_availability_checked": True, "fit_before_utc": "2030-01-01T00:00:00+00:00",
                                   "time_contract": c.TIME_CONTRACT},
             "supported_played_training_rows": 4, "excluded_unsupported_or_not_played_rows": 1,
             "participation": PARTICIPATION.copy(), "fallback_rows": 1, "abstention_rows": 0,
             "global_prior": deepcopy(prior), "position_priors": deepcopy(node["position_priors"])}
    if dist is not None:
        audit["distribution_fit"] = deepcopy(dist)
    config = {"model_version": MODEL_VERSION, "target": target, "method": method,
              "registered_methods": list(METHODS), "registered_targets": list(TARGETS),
              "seed": SEED, "ridge_alpha": RIDGE_ALPHA, "ensemble_weights": [.5, .25, .25]}
    binding = {"version": VERSION, "code_sha256": code_hashes(),
               **{key: "a" * 64 for key in ("policy_sha256", "source_manifest_sha256", "snapshot_sha256",
                   "training_view_sha256", "input_sha256", "training_features_sha256", "query_sha256")}}
    columns = sorted(c.IDENTITY_COLUMNS | set(summary))
    payload = {"schema": "nfl-model-artifact-v1", "model_version": MODEL_VERSION, "target": target,
               "method": method, "inference": node, "participation": {"kind": "unavailable"}, "distribution": dist,
               "training_audit": audit, "config": config, "config_sha256": c._digest(config),
               "code_sha256": _code_hashes(), "environment": _environment(), "contains_raw_training_rows": False,
               "source_schema": {"required_columns": columns, "numeric_columns": sorted(summary),
                                 "qualification": c.QUALIFICATION, "missing_values": c.MISSING_VALUES},
               "replayable": True, "replay_limitation": None, "evidence_state": c.EVIDENCE,
               "operational_source_binding": binding, "research_registration_sha256": "b" * 64}
    return {"artifact": payload, "sha256": c._digest(payload)}


def write(path, wrapper):
    wrapper["sha256"] = c._digest(wrapper["artifact"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(wrapper, allow_nan=False))
    return path


def query(target, method):
    window = 3 if method == "recent" else 8
    return pd.DataFrame({"player_id": ["fictional-a", "fictional-b", "fictional-c"],
        "game_id": ["fictional-game"] * 3, "position": ["QB", "QB", "unseen-query-role"],
        "team": ["FIC"] * 3, "opponent": ["TST"] * 3, "kickoff_utc": ["2030-01-01T00:00:00Z"] * 3,
        f"f_player_{target}_mean{window}": [.5 if target == "anytime_td" else 6., np.nan, 0.],
        f"f_player_{target}_n{window}": [2., np.nan, 0.]}, index=[8, 3, 11])


@pytest.mark.parametrize("target,method,dispersion", [
    ("pass_yd", "recent", 4.), ("rush_yd", "pooled", 4.),
    ("pass_td", "recent", .5), ("rec", "pooled", 0.), ("anytime_td", "pooled", 0.),
])
def test_independent_all_columns_and_literal_shrinkage(tmp_path, target, method, dispersion):
    wrapper = fictional(target, method, dispersion)
    path = write(tmp_path / "reference.json", wrapper)
    q = query(target, method)
    expected = predict_artifact(path, q, input_manifest={"source_qualified": True,
        "availability_verified": True, "input_sha256": "a" * 64})
    actual = c.independent_reference(path, q)
    pd.testing.assert_frame_equal(actual, expected, check_exact=False, rtol=1e-10, atol=1e-9)
    strength = 3 if method == "recent" else 5
    value, prior = (.5, .25) if target == "anytime_td" else (6., 2.)
    assert actual.iloc[0]["mean"] == (value * 2 + strength * prior) / (2 + strength)
    assert actual["p_participation"].isna().all()
    assert list(actual["fallback"]) == ["", "position_prior", "global_prior_unknown_position"]
    assert c.review_reference_artifact(path, target=target, method=method,
        binding=wrapper["artifact"]["operational_source_binding"])["aggregate_only"] is True


def test_signed_normal_and_supported_count_zero(tmp_path):
    path = write(tmp_path / "yards.json", fictional())
    q = query("pass_yd", "recent")
    q.iloc[0, q.columns.get_loc("f_player_pass_yd_mean3")] = -20.
    assert c.independent_reference(path, q).iloc[0]["mean"] < 0
    wrapper = fictional("rec")
    for prior in (wrapper["artifact"]["inference"]["global_prior"], wrapper["artifact"]["inference"]["position_priors"]["QB"],
                  wrapper["artifact"]["training_audit"]["global_prior"], wrapper["artifact"]["training_audit"]["position_priors"]["QB"]):
        prior["mean"] = 0.
    path = write(tmp_path / "zero.json", wrapper)
    q = query("rec", "recent")
    q["f_player_rec_mean3"] = 0.
    actual = c.independent_reference(path, q)
    assert (actual[["mean", "scale", "p10", "p50", "p90"]] == 0).all().all()


@pytest.mark.parametrize("mutation", [
    lambda p: p.update(raw_training_rows=[["private-player", 12]]),
    lambda p: p["inference"].update(query_rows=[["private-player", 12]]),
    lambda p: p["inference"]["global_prior"].update(row_values=[1, 2, 3]),
    lambda p: p["training_audit"].update(player_id="private-player"),
    lambda p: p["distribution"].update(residuals=[1., 2.]),
    lambda p: p["operational_source_binding"].update(source_path="private-source"),
    lambda p: p["source_schema"].update(rows=[]),
    lambda p: p["participation"].update(global_rate=.99),
    lambda p: p["environment"].update(private_path="private-source"),
    lambda p: p["inference"]["position_priors"].update({"private-player": {"mean": 1., "variance": 1., "n": 1}}),
    lambda p: p["training_audit"].update(historical_method_status="private-source"),
    lambda p: p["operational_source_binding"]["code_sha256"].update({"extra.py": "a" * 64}),
    lambda p: p["inference"]["global_prior"].update(n=True),
    lambda p: p["inference"]["global_prior"].update(n=0),
    lambda p: p["inference"]["global_prior"].update(variance=-1),
])
def test_unknown_nested_content_and_bad_parameters_rejected(tmp_path, mutation):
    wrapper = fictional()
    mutation(wrapper["artifact"])
    path = write(tmp_path / "bad.json", wrapper)
    with pytest.raises(ArtifactError):
        c.review_reference_artifact(path)


def test_binding_identity_corruption_duplicate_and_nonfinite_fail_closed(tmp_path):
    wrapper = fictional()
    path = write(tmp_path / "valid.json", wrapper)
    with pytest.raises(ArtifactError, match="target/method"):
        c.review_reference_artifact(path, target="rec")
    changed = deepcopy(wrapper["artifact"]["operational_source_binding"])
    changed["snapshot_sha256"] = "c" * 64
    with pytest.raises(ArtifactError, match="binding mismatch"):
        c.review_reference_artifact(path, binding=changed)
    for body in ('{"artifact":{},"artifact":{},"sha256":"a"}', '{"artifact":{"mean":NaN},"sha256":"a"}'):
        path.write_text(body)
        with pytest.raises(ArtifactError):
            c.review_reference_artifact(path)
    write(path, wrapper)
    original = path.read_bytes()
    wrapper["artifact"]["inference"]["global_prior"]["mean"] = 99.
    path.write_text(json.dumps(wrapper))
    with pytest.raises(ArtifactError, match="checksum"):
        c.review_reference_artifact(path)
    path.write_bytes(original)
    assert c.review_reference_artifact(path)["aggregate_only"] is True


def test_publication_selects_only_explicit_reviewed_artifacts(tmp_path):
    state = tmp_path / "state"
    path = write(state / "models/reference.json", fictional())
    private = state / "private-query.json"
    private.write_text('{"player_id":"private-player","rows":[1,2,3]}')
    reviewed = {"models/reference.json": sha256(path.read_bytes()).hexdigest()}
    manifest = c.build_publication_manifest(state, reviewed, policy_sha256="a" * 64, review_state="ACCEPTED")
    assert set(manifest) == {"schema_version", "review_state", "policy_sha256", "files"}
    assert manifest["files"] == reviewed
    assert set(state.iterdir()) == {state / "models", private}
    for files, policy, status in [(reviewed, "a" * 64, "PENDING"), ({"../escape.json": "a" * 64}, "a" * 64, "ACCEPTED"),
                                  ({"private-query.json": sha256(private.read_bytes()).hexdigest()}, "a" * 64, "ACCEPTED"),
                                  (reviewed, "b" * 64, "ACCEPTED"), ({"models/reference.json": "b" * 64}, "a" * 64, "ACCEPTED")]:
        with pytest.raises(ArtifactError):
            c.build_publication_manifest(state, files, policy_sha256=policy, review_state=status)
    (state / "alias.json").symlink_to(path)
    with pytest.raises(ArtifactError):
        c.build_publication_manifest(state, {"alias.json": reviewed["models/reference.json"]},
                                     policy_sha256="a" * 64, review_state="ACCEPTED")
