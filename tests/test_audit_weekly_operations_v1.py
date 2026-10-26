"""Fictional metadata only: no models, outcome panels, HTTP or native authority."""
from copy import deepcopy
from datetime import timedelta
from pathlib import Path

import pytest

from nfl_lab import audit_weekly_operations_v1 as o, audit_weekly_grade_v1 as grade
from nfl_lab import audit_weekly_epoch_v1 as epoch, gha_private_checkpoint as cp, state
from nfl_lab.operational_storage import OperationalStorage
from test_audit_weekly_epoch_v1 import fixture, prepare, registered, continuation, CONTINUED


def test_calendar_independent_DST_offsets_aliases_and_poison_outcomes():
    raw = ("season,week,game_type,game_id,gameday,gametime,espn,home_team,away_team,home_score\n"
        "2026,7,REG,london,2026-10-25,09:30,111,LA,SF,DO_NOT_PARSE_OUTCOME\n"
        "2026,10,REG,november,2026-11-15,13:00,222,LA,SF,DO_NOT_PARSE_OUTCOME\n").encode()
    a=o.calendar(raw,season=2026,week=7)[0];b=o.calendar(raw,season=2026,week=10)[0]
    assert a["kickoff_utc"]=="2026-10-25T13:30:00+00:00" and b["kickoff_utc"]=="2026-11-15T18:00:00+00:00"
    assert a["home"]=="LAR" and a["away"]=="SF" and a["website_game_id"]=="111"
    assert not any("score" in key or "outcome" in key for key in a)


@pytest.mark.parametrize("day,time",[("2026-03-08","02:30"),("2026-11-01","01:30"),("2026-10-25","")])
def test_unknown_or_DST_ambiguous_kickoff_cannot_be_assumed(day,time):
    raw=("season,week,game_type,game_id,gameday,gametime,espn,home_team,away_team\n"
        f"2026,7,REG,fictional,{day},{time},111,LA,SF\n").encode()
    with pytest.raises(o.OperationsError):o.calendar(raw,season=2026,week=7)


@pytest.mark.parametrize("duplicate",["game","espn"])
def test_complete_calendar_rejects_conflicting_identifiers(duplicate):
    line="2026,7,REG,one,2026-10-25,13:00,111,CHI,GB\n"
    second="2026,7,REG,"+("one" if duplicate=="game" else "two")+",2026-10-25,16:00,"+("222" if duplicate=="game" else "111")+",MIN,DET\n"
    raw=("season,week,game_type,game_id,gameday,gametime,espn,home_team,away_team\n"+line+second).encode()
    with pytest.raises(o.OperationsError,match="UNIQUE_FULL_WEEK"):o.calendar(raw,season=2026,week=7)


def test_closed_context_cannot_carry_values_or_a_self_supplied_private_body():
    value=dict(schema_version=o.CONTEXT_SCHEMA,controller_context=None,
        previous_capture=dict(feed_sha256="a"*64,receipt_sha256="b"*64))
    assert o.context(value)==value
    for key in ("forecast_rows","private_template","root_go"):
        changed=dict(value,**{key:[]})
        with pytest.raises(o.OperationsError,match="CLOSED_RECURRING"):o.context(changed)


def model_roles_fixture(tmp_path):
    root=Path(__file__).resolve().parents[1]
    storage=OperationalStorage(tmp_path/"cache",root/"config/operational-source-policy-v2.json",state=tmp_path/"state")
    output=storage.register_root(tmp_path/"metadata");refs=[]
    for n,(target,family,method) in enumerate(cp.JOBS):
        roles=["QB"] if target.startswith("pass_") else ["QB","RB","FB","WR","TE"]
        doc=dict(category=dict(target=target,modeled_roles=roles,primary_roles=["QB"] if target.startswith("pass_") else ["RB"]),family=family,method_id=method)
        refs.append(o.archive.write(storage,output/(str(n)+".json"),doc))
    document={key:None for key in o.resume.MODEL_KEYS}
    document.update(state="CROSS_RUN_EFFECTIVE18_RESTORED_AND_REPLAYED_PRIVATE",model_pairs=18,fits=0,
        current_loader_replay=True,model_artifact_durability=True,models=refs)
    return storage,output,document


def test_manifest_roles_require_live_caller_and_all18_exact_slots(tmp_path):
    storage,output,doc=model_roles_fixture(tmp_path)
    ref=o.archive.write(storage,output/"RESTORED.json",doc)
    with pytest.raises(o.OperationsError,match="LIVE_CURRENT_MODEL"):o.roles_from_manifests(storage,ref,authenticate=lambda _:False)
    roles=o.roles_from_manifests(storage,ref,authenticate=lambda _:True)
    assert set(roles)==set(cp.TARGETS) and roles["pass_yd"]["primary_roles"]==["QB"]
    assert roles["rush_att"]["modeled_roles"]==["QB","RB","FB","WR","TE"]
    bad=deepcopy(doc);bad["models"][0],bad["models"][1]=bad["models"][1],bad["models"][0]
    badref=o.archive.write(storage,output/"BAD.json",bad)
    with pytest.raises(o.OperationsError,match="MANIFEST_ROLE_IDENTITY"):o.roles_from_manifests(storage,badref,authenticate=lambda _:True)


def test_different_model_roles_cannot_silently_change_grading_population(tmp_path):
    storage,output,doc=model_roles_fixture(tmp_path)
    n=next(i for i,x in enumerate(cp.JOBS)if x[2]=="COUNT_A")
    original=o.cp.strict_json(o.cp.read_ref(doc["models"][n]));original["category"]["primary_roles"]=["WR"]
    doc["models"][n]=o.archive.write(storage,output/"ROLE_CHANGE.json",original)
    ref=o.archive.write(storage,output/"RESTORED.json",doc)
    with pytest.raises(o.OperationsError,match="SHARE_REGISTERED_CATEGORY_ROLES"):o.roles_from_manifests(storage,ref,authenticate=lambda _:True)


def test_refresh_preserves_primary_assignment_without_another_observation():
    f=fixture();r=registered(prepare(f));c=continuation(f,r)
    roles={t:dict(modeled_roles=["QB"] if t.startswith("pass_") else ["RB"],primary_roles=["QB"] if t.startswith("pass_") else ["RB"])for t in cp.TARGETS}
    at=CONTINUED+timedelta(minutes=1)
    first,decision=o.primary_population(r,c,roles,capture_id="a"*64,authenticate=lambda _:True,clock=lambda:at)
    assert decision["state"]=="FIRST_PREVALUE_PRIMARY_CAPTURE"
    # This is a fictional typed prior state for metadata composition only. It
    # supplies no native/durability authority and opens no forecast body.
    prior=grade.DurableHistory(dict(epoch_sha256=r.epoch.sha256,captures=[dict(population=first.document)]),grade._KEY)
    second,decision=o.primary_population(r,c,roles,capture_id="b"*64,authenticate=lambda _:True,
        previous=prior,clock=lambda:at+timedelta(minutes=1))
    assert decision["state"]=="REFRESH_NOT_ANOTHER_PRIMARY_OBSERVATION" and not decision["primary_game_ids"]
    assert second.document["assignments"]==first.document["assignments"] and set(second.document["assignments"].values())=={"a"*64}
    assert first.document["registered_at"]!=second.document["registered_at"]
    with pytest.raises(grade.GradeError,match="AUTHENTICATION_REJECTED"):
        o.primary_population(r,c,roles,capture_id="b"*64,authenticate=lambda _:False,clock=lambda:at)
