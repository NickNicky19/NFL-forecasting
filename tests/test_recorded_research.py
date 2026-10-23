"""Fictional point contracts only; no NFL source or accuracy evaluation."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest

from nfl_lab import recorded_research as recorded
from nfl_lab.consumer import consumer_forecast, consumer_research_point
from nfl_lab.evaluation import summarize
from nfl_lab.prospective import score_saved
from nfl_lab.receiving import SourceDocument
from nfl_lab.state import append_outcomes, capture, digest, records, save, validate_forecast
from nfl_lab.website_baselines import capture_website_bindings


def fictional_sources(*, change=None):
    now = datetime.now(timezone.utc)
    context = dict(player_id="fictional-gsis", game_id="fictional-future", team="A", opponent="B",
        season=2026, season_type="REG", week=8, period="full_game_with_ot",
        cutoff_at=(now-timedelta(minutes=1)).isoformat(), kickoff_at=(now+timedelta(days=1)).isoformat(),
        projection_observed_at=(now-timedelta(minutes=2)).isoformat(), website_yards=40.5,
        website_attempts=20.5, baseline_receipt_sha256="a"*64, projection_source_ref="fictional-original")
    header = {k: context[k] for k in ("player_id", "season", "season_type", "period")}
    schedule = dict(**header, through_week=7, weeks=[])
    stats = dict(**header, records=[])
    for week in range(1,8):
        prior = now-timedelta(days=7*(8-week))
        game = dict(week=week,state="game",game_id=f"fictional-{week}",team="A",opponent="C",
            kickoff_at=prior.isoformat(),completed=True,final_observed_at=(prior+timedelta(hours=4)).isoformat())
        schedule["weeks"].append(game)
        stats["records"].append(dict(**header,**{k:game[k] for k in (
            "week","game_id","team","opponent","kickoff_at")},pass_att=10,pass_yd=-20,
            participation="played",stats_observed_at=(prior+timedelta(hours=5)).isoformat(),source_ref="fictional-stats"))
    projection = {**context,"attempts_origin":"same_receipt_unchanged_website","sleeper_id":"fictional-sleeper","position":"QB"}
    if change:
        change(context,schedule,stats,projection)
    docs, pins = {}, {}
    for role,ref,payload in (("opportunities","fictional-schedule",schedule),
        ("statistics","fictional-stats",stats),("projection","fictional-original",projection)):
        doc = SourceDocument(ref,json.dumps(payload).encode(),projection["projection_observed_at"])
        docs[role] = doc
        pins[ref] = hashlib.sha256(doc.payload).hexdigest()
    return context,docs,pins


def prepare(*,change=None):
    context,docs,pins=fictional_sources(change=change)
    return recorded.prepare_recorded_point(context,**docs,trusted_hashes=pins)


def issued(row):
    return {**deepcopy(row),"issued_at":datetime.now(timezone.utc).isoformat()}


def test_prepare_preserves_signed_point_and_frozen_arithmetic_contract():
    row=prepare()
    assert row["point"]==-41 and "mean" not in row
    assert row["prediction_functional"]==recorded.FUNCTIONAL
    result=row["research_result"]
    assert result["calculation_lane"]=="AFTER_CUTOFF_UNRECORDED_ARITHMETIC"
    assert not result["recorded_pregame"] and not result["qualified_for_default"]
    assert row["research_result_sha256"]==digest(result)
    assert row["input_sha256"]==result["input_sha256"]
    assert row["research_module_sha256"]==result["code_sha256"]
    assert row["code_sha256"]==recorded.source_tree_digest(recorded.ROOT)
    assert row["recorded_schema_sha256"]==hashlib.sha256(recorded.SCHEMA.read_bytes()).hexdigest()
    assert row["sleeper_id"]=="fictional-sleeper" and row["position"]=="QB"
    assert "issued_at" not in row
    recorded.validate_recorded_point(row,require_issued=False)
    original=issued(row);copy=deepcopy(original)
    consumer=consumer_forecast(original)
    assert original==copy and consumer["point"]==-41 and "mean" not in consumer
    assert consumer["derived_from_original_row_sha256"]==digest(original)


@pytest.mark.parametrize("field,value",[("mean",1),("family","normal"),("scale",1),
    ("p50",0),("probability",.5),("p_participation",.9),("distribution",None)])
def test_point_rejects_mean_distribution_and_probability_hybrids(field,value):
    row=issued(prepare());row[field]=value
    with pytest.raises(Exception):validate_forecast(row)


@pytest.mark.parametrize("value",[None,True,float("nan"),float("inf")])
def test_point_requires_finite_signed_number(value):
    row=issued(prepare());row["point"]=value
    with pytest.raises(Exception):validate_forecast(row)


def test_mean_legacy_accepted_but_unknown_explicit_functionals_and_hybrids_rejected():
    row=dict(player_id="p",game_id="g",team="A",opponent="B",target="pass_yd",model_id="legacy",
        scoring_id="s",input_sha256="a"*64,code_sha256="b"*64,
        issued_at="2000-01-01T00:00:00Z",kickoff_utc="2000-01-02T00:00:00Z",mean=-2)
    validate_forecast(row)
    validate_forecast({**row,"prediction_functional":"conditional_played_mean"})
    for functional in [None,"median","other"]:
        with pytest.raises(ValueError):validate_forecast({**row,"prediction_functional":functional})
    with pytest.raises(ValueError):validate_forecast({**row,"point":-2})


@pytest.mark.parametrize("field",["research_result_sha256","input_sha256","model_config_sha256",
    "research_module_sha256","recorded_schema_sha256","research_schema_sha256","baseline_receipt_sha256"])
def test_hash_or_lineage_mismatch_rejected(field):
    row=issued(prepare());row[field]="0"*64
    with pytest.raises(Exception):consumer_research_point(row)


@pytest.mark.parametrize("field",["player_id","game_id","team","opponent","season","week","sleeper_id","position"])
def test_result_identity_cannot_be_overridden(field):
    row=issued(prepare());row[field]=2027 if field=="season" else 9 if field=="week" else "other"
    with pytest.raises(Exception):validate_forecast(row)


def test_actual_code_change_during_preparation_fails(monkeypatch):
    calls=iter(["a"*64,"b"*64])
    monkeypatch.setattr(recorded,"source_tree_digest",lambda root:next(calls))
    with pytest.raises(ValueError,match="source changed"):prepare()


@pytest.mark.parametrize("release",["SCHEMA","RESEARCH_SCHEMA","CONFIG"])
@pytest.mark.parametrize("phase",["after_calculation","after_validation"])
def test_release_pin_changes_during_prepare_fail_closed(monkeypatch,release,phase):
    target=getattr(recorded,release);original_sha=recorded._sha
    original_validate=recorded.validate_recorded_point
    state={"reads":0,"validated":False}
    def changing_sha(path):
        if Path(path)==target:
            state["reads"]+=1
            if (phase=="after_calculation" and state["reads"]>1) or state["validated"]:
                return "0"*64
        return original_sha(path)
    def validate_then_change(*args,**kwargs):
        original_validate(*args,**kwargs)
        state["validated"]=True
    monkeypatch.setattr(recorded,"_sha",changing_sha)
    if phase=="after_validation":
        monkeypatch.setattr(recorded,"validate_recorded_point",validate_then_change)
    with pytest.raises(ValueError,match="source changed"):prepare()


def test_private_source_values_are_not_copied_into_prepared_or_saved_envelope(tmp_path):
    sentinel="FICTIONAL_PRIVATE_SOURCE_SENTINEL_91824"
    def private(c,s,t,p):
        for payload in (c,s,t,p):payload["private_raw_payload"]=sentinel
    row=prepare(change=private)
    assert sentinel not in json.dumps(row)
    capture(tmp_path,[row])
    assert sentinel not in json.dumps(list(records(tmp_path,"forecasts")))


def test_missing_projection_metadata_abstains_and_fallback_stays_literal():
    fallback=prepare(change=lambda c,s,t,p:t["records"][-1].update(participation="unknown"))
    assert fallback["point"]==40.5 and fallback["fallback"]=="intervening_unknown_participation"
    assert fallback["research_result"]["state"]=="UNCHANGED_WEBSITE_FALLBACK"
    assert prepare(change=lambda c,s,t,p:p.update(attempts_origin="challenger")) is None
    with pytest.raises(Exception):prepare(change=lambda c,s,t,p:p.pop("sleeper_id"))
    with pytest.raises(Exception):prepare(change=lambda c,s,t,p:p.pop("position"))


@pytest.mark.parametrize("field",["feature_cutoff_utc","calculation_started_at","calculation_completed_at","issued_at"])
def test_calculation_and_issuance_chronology_enforced(field):
    row=issued(prepare())
    row[field]=(datetime.fromisoformat(row["kickoff_utc"])+timedelta(seconds=1)).isoformat()
    with pytest.raises(Exception):validate_forecast(row)


def test_future_cutoff_and_retrospective_calculation_are_unrecordable():
    def future(c,s,t,p):
        c["cutoff_at"]=p["cutoff_at"]=(datetime.now(timezone.utc)+timedelta(minutes=1)).isoformat()
    with pytest.raises(ValueError,match="chronology"):prepare(change=future)
    def old(c,s,t,p):
        c["kickoff_at"]=p["kickoff_at"]=(datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat()
    with pytest.raises(ValueError):prepare(change=old)


def test_capture_retry_publication_and_point_replay_never_register_confirmation(tmp_path):
    row=prepare();result=capture(tmp_path,[row])
    saved=next(records(tmp_path,"forecasts"))["rows"][0]
    assert saved["research_result_sha256"]==row["research_result_sha256"] and "issued_at" not in row
    assert capture(tmp_path,[row])["duplicates"]==1
    assert score_saved(tmp_path)["forecast_counts"]["local_only"]==1
    save(tmp_path,"publication",dict(batch=result["batch"],observed_remote_readback_at=datetime.now(timezone.utc).isoformat()))
    assert score_saved(tmp_path)["forecast_counts"]["pending"]==1
    append_outcomes(tmp_path,[dict(player_id=row["player_id"],game_id=row["game_id"],target="pass_yd",
        actual=-40,participation_state="played",source="fictional",source_sha256="d"*64,
        observed_at=datetime.now(timezone.utc).isoformat(),source_timestamp=None)])
    summary=score_saved(tmp_path)["categories"][0]
    assert summary["mae"]==1 and summary["bias"]==-1
    assert summary["cohort"]=="unqualified_shadow_no_confirmation_registration"
    assert summary["confirmation_state"]=="UNREGISTERED_UNQUALIFIED_SHADOW"
    assert not any(k in summary for k in ("normal","negbin","calibration","participation_brier"))


def test_late_capture_and_publication_are_not_scored(tmp_path):
    row=prepare();late=datetime.fromisoformat(row["kickoff_utc"])+timedelta(seconds=1)
    result=capture(tmp_path,[row],clock=lambda:late)
    assert result["recorded"]==0 and result["missed"]==1
    assert score_saved(tmp_path)["categories"]==[]
    timely=tmp_path/"timely";result=capture(timely,[row])
    save(timely,"publication",dict(batch=result["batch"],observed_remote_readback_at=late.isoformat()))
    assert score_saved(timely)["forecast_counts"]["late"]==1


def test_point_summarize_is_explicit_and_does_not_create_mean():
    frame=pd.DataFrame([dict(participation_state="played",actual=-1,point=-3,fallback=None,
        game_id="g",player_id="p",season=2026,week=8)])
    original=frame.copy(deep=True)
    result=summarize(frame,value_column="point",include_distribution=False)
    assert result["mae"]==2 and result["bias"]==-2
    pd.testing.assert_frame_equal(frame,original)
    with pytest.raises(ValueError):summarize(frame,value_column="point")
    with pytest.raises(ValueError):summarize(frame,value_column="median",include_distribution=False)


def test_website_bindings_explicitly_exclude_recorded_points(tmp_path):
    row=prepare();result=capture(tmp_path,[row])
    prepared=dict(report={"state":"READY"},header={},_private_points={})
    bound=capture_website_bindings(tmp_path,prepared,result["batch"])
    assert bound["bound"]==0
    assert bound["binding_exclusions"]=={"research_point_comparator_binding_not_implemented":1,"missed_during_calculation":0}
    assert list(records(tmp_path,"website_bindings"))==[]


def test_frozen_files_defaults_and_rec_half_are_unchanged():
    config=json.loads(Path("config/research.json").read_text())
    assert config["operations"]["default_daily_methods"]==["recent","pooled"]
    from nfl_lab.models import METHODS
    assert recorded.research_passing.METHOD not in METHODS
    preserved=json.loads(Path("config/preserved-rec-half-registration.json").read_text())
    assert preserved["recording_status"]=="OFFLINE_NOT_ACTIVATED"
    assert preserved["protocol"]["window"]["weeks"]==list(range(7,15))
