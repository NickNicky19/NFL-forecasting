"""Five fictional source-only checks, curated from the executed six-check suite.

The private runner import, freeze_member/controller fixture and full synthetic
runner fixture are omitted. This derivative checks the unchanged public
calibrator and context-alignment source; it is not an execution-controller test
or a new NFL experiment. See reports/anytime-calibration-v1/README.md.
"""
from copy import deepcopy
import json

import numpy as np
import pandas as pd
import pytest
from scipy.special import expit, logit

from nfl_lab.anytime_calibration import (
    METHODS, Calibrator, align_context, binary_losses, probabilities,
)


def test_known_binary_endpoint_losses_and_no_probability_clipping():
    p=np.array([0.,1.,0.,1.,.25,.75,np.nan])
    y=np.array([0.,1.,1.,0.,1.,0.,1.])
    brier,loss=binary_losses(p,y)
    np.testing.assert_allclose(brier[:6],[0,0,1,1,.75**2,.75**2],atol=0)
    np.testing.assert_allclose(loss[[0,1,4,5]],[0,0,np.log(4),np.log(4)])
    assert np.isposinf(loss[[2,3]]).all() and np.isnan(loss[6])
    for bad in [[-.001],[1.001],[np.inf]]:
        with pytest.raises(ValueError,match="no clipping"):probabilities(bad)


def test_all_four_fixed_methods_are_monotone_and_minimize_declared_training_objective():
    rng=np.random.default_rng(1931)
    p=np.tile(np.linspace(.02,.98,100),12)
    y=(rng.random(len(p))<expit(.7+1.2*logit(p))).astype(float)
    grid=np.r_[0.,np.linspace(.001,.999,1000),1.]
    original=binary_losses(p,y)[1].mean()
    for method in METHODS:
        model=Calibrator.fit(p,y,method)
        assert model.audit["state"]=="FITTED"
        q=model.predict(grid)
        assert (np.diff(q)>=0).all() and ((q>=0)&(q<=1)).all()
        if method!="isotonic":
            assert q[0]==0 and q[-1]==1
            assert np.asarray(model.parameters[1:]).min(initial=0)>=0
            measured=binary_losses(model.predict(p),y)[1].mean()+.005*np.sum((np.array(model.parameters[1:])-1)**2)
            assert measured==pytest.approx(model.audit["objective"],abs=2e-12)
            assert measured<=original+1e-10
            assert model.audit["iterations"]<=200 and model.audit["optimizer_attempts"]==1


def test_identity_shrinkage_unpenalized_intercept_and_serialization_replay():
    p=np.full(500,.4);y=np.tile([0.,0.,0.,1.,1.],100)
    grid=np.r_[0.,.1,.4,.9,1.,np.nan]
    for method in METHODS:
        model=Calibrator.fit(p,y,method)
        assert model.audit["state"]=="FITTED" and not model.audit["intercept_penalized"]
        restored=Calibrator.from_manifest(json.loads(json.dumps(model.manifest(),allow_nan=False)))
        np.testing.assert_array_equal(model.predict(grid),restored.predict(grid))
        if method!="isotonic":
            np.testing.assert_allclose(model.parameters,[0.]+[1.]*(len(model.parameters)-1),atol=1e-12)
            assert model.audit["objective"]==pytest.approx(-.4*np.log(.4)-.6*np.log(.6))
            if method=="platt":
                invalid=deepcopy(model.manifest());invalid["parameters"][1]=-1.
                with pytest.raises(ValueError,match="constrained"):Calibrator.from_manifest(invalid)


def test_support_thresholds_and_method_specific_endpoint_training_behavior():
    short_p=np.linspace(.1,.9,199);short_y=np.arange(199)%2
    for method in METHODS:
        model=Calibrator.fit(short_p,short_y,method)
        assert model.audit["reason"]=="insufficient_calibration_rows_or_classes"
        np.testing.assert_array_equal(model.predict(short_p),short_p)
        model=Calibrator.fit(np.full(300,.4),np.r_[np.ones(29),np.zeros(271)],method)
        assert model.audit["state"]=="UNCHANGED_BASE_FALLBACK"
    p=np.r_[np.zeros(100),np.ones(100),np.full(100,.5)]
    y=np.r_[np.ones(100),np.zeros(100),np.arange(100)%2]
    for method in METHODS[:3]:
        model=Calibrator.fit(p,y,method)
        assert model.audit["attempt_charged"] and model.audit["optimizer_attempts"]==0
        assert model.audit["reason"]=="irreducible_infinite_endpoint_training_NLL"
        np.testing.assert_array_equal(model.predict(p),p)
    iso=Calibrator.fit(p,y,"isotonic")
    assert iso.audit["state"]=="FITTED"
    np.testing.assert_allclose(iso.predict([0,.2,1]),.5)


def test_same_source_context_alignment_rejects_missing_offers_cutoffs_and_duplicates():
    context=pd.DataFrame(dict(season=[2023,2023,2023],week=[1,1,1],game_id=["fiction-z","fiction-a","fiction-m"],
        player_id=["p2","p1","p3"],team="fiction-A",opponent="fiction-B",position="WR",
        kickoff_utc="2023-09-01T12:00:00Z",cutoff_utc="2023-09-01T10:00:00Z"))
    source=context.assign(probability=[.2,.4,.6]).iloc[[2,0,1]]
    np.testing.assert_array_equal(align_context(context,source).probability,[.2,.4,.6])
    for changed in [source.iloc[:2],pd.concat([source,source.iloc[:1]])]:
        with pytest.raises(ValueError):align_context(context,changed)
    changed=source.copy();changed.loc[0,"cutoff_utc"]="2023-09-01T10:01:00Z"
    with pytest.raises(ValueError,match="cutoff"):align_context(context,changed)
