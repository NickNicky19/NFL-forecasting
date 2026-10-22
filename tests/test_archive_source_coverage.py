import json

import numpy as np
import pandas as pd
import pytest

from nfl_lab.archive_source_coverage import PREDICTION_COLUMNS, apply_outcomes, frozen_facts, resolve_sources
from nfl_lab.archive_study import assert_unused_registration, run


def candidate(value=0.,state="played",status="supported",gap=None):
    return {"actual":value,"participation_state":state,"supplement_status":status,"gap_reason":gap}


def test_explicit_qualified_zero_expands_coverage_without_rewriting_missing_sleeper():
    result=resolve_sources("pass_int",np.nan,"played",candidate())
    assert result["actual"]==0. and result["resolution"]=="expanded_nflverse_supported"
    assert result["sleeper_actual"] is None
    assert result["participation_state"]=="played" and not result["quarantined"]


def test_missing_rare_count_is_never_filled_with_zero_without_supported_source():
    result=resolve_sources("pass_int",None,"played",candidate(None,status="unsupported",gap="target_statistic_missing"))
    assert result["actual"] is None and result["resolution"]=="unresolved_missing_sources"
    unqualified=resolve_sources("pass_int",None,"played",candidate(0.,status="unsupported"))
    assert unqualified["actual"] is None


def test_signed_yards_and_equal_sources():
    result=resolve_sources("rush_yd",-3.,"played",candidate(-3.))
    assert result["actual"]==-3. and result["resolution"]=="dual_source_agreement"


@pytest.mark.parametrize("value",[-1.,1.5,np.inf])
def test_invalid_count_does_not_enter_scoring(value):
    result=resolve_sources("pass_int",None,"played",candidate(value))
    assert result["quarantined"] and result["actual"] is None


def test_numeric_and_participation_conflicts_have_no_source_winner():
    conflict=resolve_sources("pass_int",1.,"played",candidate(0.))
    assert conflict["actual"] is None and conflict["resolution"]=="quarantined_numeric_conflict"
    for original_state,nfl_state in [("played","DNP"),("DNP","played")]:
        conflict=resolve_sources("pass_int",None,original_state,candidate(None,nfl_state,"unsupported"))
        assert conflict["actual"] is None and conflict["participation_state"]=="unknown"
        assert conflict["resolution"]=="quarantined_participation_conflict"


def test_supported_original_retained_with_explicit_supplement_gap():
    result=resolve_sources("pass_int",1.,"played",candidate(None,"unknown","unsupported","identity_gap"))
    assert result["actual"]==1. and result["nflverse_gap"]=="identity_gap"
    assert result["resolution"]=="sleeper_supported_nflverse_gap"


def fixture():
    key={"season":2026,"week":6,"game_id":"g","player_id":"sleeper:1","target":"pass_int"}
    methods=["raw_sleeper","pinned_website","lab_recent","lab_pooled","lab_selected"]
    rows=pd.DataFrame([{**key,"method":method,"actual":np.nan,"participation_state":"played",**{c:None for c in PREDICTION_COLUMNS}} for method in methods])
    rows["mean"]=1.;rows["scale"]=1.;rows["family"]="negbin";rows["fallback"]="saved_fallback"
    cohort=pd.DataFrame([{**key,"sleeper_id":"1","canonical_player_id":"00-1234567","team":"A","opponent":"B","kickoff_utc":"2026-10-18T13:30:00Z","cutoff_utc":"2026-10-18T10:48:59Z"}])
    return rows,cohort,methods,key


def test_frozen_method_support_and_actuals_must_be_identical():
    rows,cohort,methods,_=fixture()
    facts=frozen_facts(rows,cohort,["pass_int"],methods,{"season":2026,"week":6})
    assert len(facts)==1 and facts.actual.isna().all()
    changed=rows.copy();changed.loc[0,"actual"]=0.
    with pytest.raises(ValueError,match="source facts"):
        frozen_facts(changed,cohort,["pass_int"],methods,{"season":2026,"week":6})
    with pytest.raises(ValueError,match="missing or unexpected"):
        frozen_facts(rows.iloc[:-1],cohort,["pass_int"],methods,{"season":2026,"week":6})
    with pytest.raises(ValueError,match="duplicate"):
        frozen_facts(pd.concat([rows,rows.iloc[[0]]]),cohort,["pass_int"],methods,{"season":2026,"week":6})


def test_variant_preserves_predictions_unsupported_rows_and_original_facts():
    rows,_,_,key=fixture()
    unsupported=rows.iloc[[0]].copy();unsupported["target"]="fantasy_ppr"
    rows=pd.concat([rows,unsupported],ignore_index=True);before=rows.copy(deep=True)
    outcome={**key,**resolve_sources("pass_int",None,"played",candidate())}
    variant=apply_outcomes(rows,pd.DataFrame([outcome]))
    pd.testing.assert_frame_equal(rows,before)
    assert variant.actual.iloc[:5].eq(0.).all() and variant.original_actual.isna().all()
    assert pd.isna(variant.actual.iloc[-1]) and variant.source_resolution.iloc[-1]=="unsupported_unchanged"
    pd.testing.assert_frame_equal(variant[PREDICTION_COLUMNS],before[PREDICTION_COLUMNS])


def test_completed_original_registration_guard_runs_before_any_source_or_fit(tmp_path,monkeypatch):
    registration={"registration_id":"already-done"}
    (tmp_path/"config").mkdir();(tmp_path/"config/archive-lab-comparison-v1.json").write_text(json.dumps(registration))
    saved=tmp_path/"reports/original";saved.mkdir(parents=True)
    (saved/"report.json").write_text(json.dumps({"state":"COMPLETED","registration":registration,"fits_attempted":30}))
    def forbidden(*args,**kwargs):raise AssertionError("no new source or fit allowed")
    monkeypatch.setattr("nfl_lab.archive_study.fit_predict",forbidden)
    monkeypatch.setattr("nfl_lab.archive_study.read_source",forbidden)
    with pytest.raises(ValueError,match="already consumed"):
        run(tmp_path,tmp_path/"absent-cache")
    assert not (tmp_path/"runs").exists()
    assert_unused_registration(tmp_path,"unrelated")
