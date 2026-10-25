"""Fictional weekly count expectations; no fits, source data or old artifact edits."""
import copy
import hashlib
import json
import numpy as np
import pandas as pd
import pytest

from nfl_lab.cdf_engine import LeafCDFModel, SupportPrior
from nfl_lab.role_boosting import RoleCountBoostingModel
from nfl_lab import weekly_future_inference as weekly


class FixedEstimator:
    def predict(self, design):
        return np.full(len(design), 5.5)


class FixedDesign:
    def transform(self, frame):
        return np.zeros((len(frame), 1))


def fictional_model():
    category = dict(target="rush_att", state="READY", support="count",
        modeled_roles=["RB"], primary_roles=["RB"],
        panels={"base":["f_player_rush_att_mean3"],
                "context":["f_player_rush_att_mean3"]})
    prior = SupportPrior("count", q=.75)
    return RoleCountBoostingModel(category, "A",
        estimators={"pooled":FixedEstimator()}, designs={"pooled":FixedDesign()},
        priors={"RB":prior,"FB":SupportPrior("count",q=.5)},
        global_prior=SupportPrior("count",q=.8), audit={"subfits":[]})


def test_only_fallback_entries_change_and_original_model_is_preserved():
    # Geometric q=3/4: E[X]=3; F(1)=7/16<1/2 and F(2)=37/64>1/2,
    # so the frozen research model returns median 2 on the cold row.
    model = fictional_model()
    frame = pd.DataFrame({"position":["RB","RB"],"f_player_games_prior":[0.,4.]},
                         index=[91,37])
    before, reasons = model.predict(frame)
    assert before.tolist() == [2.,5.5]
    after, after_reasons = weekly._points(model,"count_A",frame)
    assert after.tolist() == [3.,5.5]
    assert after_reasons.tolist() == reasons.tolist()
    again, _ = model.predict(frame)
    np.testing.assert_array_equal(again,before)


@pytest.mark.parametrize("case,role,expected", [
    ("missing_estimator","RB",3.),
    ("nonmodeled","FB",1.),
    ("unknown_role","fictional-unknown",4.),
    ("all_zero_prior","RB",.05),
])
def test_stored_role_or_global_mean_drives_fallback(case,role,expected):
    model = fictional_model()
    if case == "missing_estimator":
        model.estimators.clear()
    if case == "all_zero_prior":
        # The registered support-prior mean floor is .05, not its median zero.
        model.priors["RB"] = SupportPrior("count",q=1/21)
        model.estimators.clear()
    frame = pd.DataFrame({"position":[role],"f_player_games_prior":[0.]})
    values,reasons = weekly._points(model,"count_A",frame)
    assert values[0] == pytest.approx(expected)
    assert reasons[0]


def test_unsupported_prior_remains_abstention():
    model = fictional_model()
    model.priors.clear()
    model.global_prior = None
    values,reasons = weekly._points(model,"count_A",
        pd.DataFrame({"position":["RB"],"f_player_games_prior":[0.]}))
    assert np.isnan(values[0])
    assert reasons[0] == "no_supported_played_training_outcomes"


def test_cdf_count_family_keeps_its_existing_mean():
    original = fictional_model()
    model = LeafCDFModel(original.category,"base",None,None,np.array([0.]),
        priors=copy.deepcopy(original.priors),global_prior=original.global_prior)
    frame = pd.DataFrame({"position":["RB"],"f_player_games_prior":[0.]})
    values,_ = weekly._points(model,"leaf_cdf_base",frame)
    assert values[0] == 3.


def test_fallback_semantics_are_explicitly_bound_to_recipe_version(monkeypatch):
    monkeypatch.setattr(weekly,"code_pins",lambda:{"fictional_code":"a"*64})
    contract = {"fictional_source":"v1"}
    revised = weekly.procedure_version("count_A",contract)
    monkeypatch.setattr(weekly,"COUNT_A_FALLBACK_VERSION","fictional-earlier-rule")
    assert weekly.procedure_version("count_A",contract) != revised


def test_old_manifest_is_rejected_before_any_model_decode(tmp_path, monkeypatch):
    # Matching source/environment alone cannot turn an older fallback receipt
    # into evidence for the new weekly product. No model body is even supplied.
    current = {"fictional_code":"a"*64}
    monkeypatch.setattr(weekly,"code_pins",lambda:current)
    monkeypatch.setattr(weekly,"environment",lambda:{"fictional_env":"v1"})
    manifest = dict(schema_version=weekly.VERSION,
        artifact_kind="TRAINED_FUTURE_QUERY_NOT_HISTORICAL_REPLAY",family="count_A",
        code_pins=current,environment={"fictional_env":"v1"})
    path = tmp_path/"fictional-old-manifest.json"
    body = json.dumps(manifest).encode();path.write_bytes(body);path.chmod(0o444)
    binding = dict(path=str(path),bytes=len(body),sha256=hashlib.sha256(body).hexdigest())
    session = weekly.FutureInferenceSession(lambda items:{r["path"]:r for r in items})
    import joblib
    def forbidden(*args,**kwargs):
        raise AssertionError("old fallback manifest must fail before decoding")
    monkeypatch.setattr(joblib,"load",forbidden)
    with pytest.raises(ValueError,match="requalification needed"):
        session.prepare([binding])
    assert session.models == {}
