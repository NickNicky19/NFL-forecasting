from datetime import datetime,timezone
import pytest
from nfl_lab.cadence import decision, PARENT_POLICY, LEGACY_POLICY


def dt(text):return datetime.fromisoformat(text.replace("Z","+00:00"))


def test_daily_dst_slots_have_one_writer():
    assert decision("schedule",now=dt("2026-10-22T13:36:00Z"))["due"]
    assert not decision("schedule",now=dt("2026-10-22T14:36:00Z"))["due"]
    assert not decision("schedule",now=dt("2026-12-10T13:36:00Z"))["due"]
    assert decision("schedule",now=dt("2026-12-10T14:36:00Z"))["due"]


def test_delayed_schedule_skips_without_backdating_and_manual_retry():
    assert decision("schedule",now=dt("2026-10-22T13:57:00Z"))["reason"]=="MISSED_SCHEDULE_WINDOW_NOT_BACKFILLED"
    assert decision("workflow_dispatch","daily",dt("2026-10-22T16:00:00Z"))["due"]
    assert decision("schedule",now=dt("2026-10-25T13:36:00Z"))["mode"]=="train"
    assert decision("push",now=dt("2026-10-25T13:36:00Z"))["mode"]=="daily"
    with pytest.raises(ValueError):decision("schedule",now=datetime(2026,10,22))


def test_delayed_and_manual_grading_never_authorize_pregame_issuance():
    delayed=decision("schedule",now=dt("2026-10-22T18:08:23Z"))
    assert delayed["due"] is False and delayed["mode"]=="grade"
    assert delayed["pregame_issuance_allowed"] is False
    manual=decision("workflow_dispatch","grade",dt("2026-10-22T18:08:23Z"))
    assert manual["mode"]=="grade" and manual["pregame_issuance_allowed"] is False
    assert decision("schedule",now=dt("2026-10-25T13:36:00Z"))["pregame_issuance_allowed"] is True


@pytest.mark.parametrize("date,parent_hour,legacy_hour", [
    ("2026-03-07",13,14),("2026-03-08",12,13),("2026-10-25",12,13),
    ("2026-10-31",12,13),("2026-11-01",13,14),("2026-12-10",13,14),
])
def test_one_shared_cron_candidate_is_due_for_each_distinct_policy(date,parent_hour,legacy_hour):
    parent_slots=[]; legacy_slots=[]
    for hour in (12,13,14):
        stamp=dt(f"{date}T{hour}:36:00Z")
        if decision("schedule",now=stamp,policy=PARENT_POLICY)["due"]:parent_slots.append(hour)
        if decision("schedule",now=stamp)["due"]:legacy_slots.append(hour)
    assert parent_slots==[parent_hour] and legacy_slots==[legacy_hour]


@pytest.mark.parametrize("clock,expected",[("12:35:59",False),("12:36:00",True),("12:56:59",True),("12:57:00",False),("13:36:00",False)])
def test_parent_window_is_0736_to_0756_without_backfill(clock,expected):
    result=decision("schedule",now=dt("2026-10-25T"+clock+"Z"),policy=PARENT_POLICY)
    assert result["due"] is expected and result["policy_version"]==PARENT_POLICY
    assert result["mode"]==("daily" if expected else "grade")


def test_parent_policy_preserves_owner_manual_semantics_and_cannot_select_training():
    assert decision("workflow_dispatch","daily",dt("2026-10-25T17:23:00Z"),policy=PARENT_POLICY)["due"]
    assert decision("schedule",now=dt("2026-10-25T12:36:00Z"),policy=PARENT_POLICY)["mode"]=="daily"
    assert decision("schedule",now=dt("2026-10-25T13:36:00Z"),policy=LEGACY_POLICY)["mode"]=="train"
    with pytest.raises(ValueError):decision("schedule",now=dt("2026-10-25T12:36:00Z"),policy="unknown")
    with pytest.raises(ValueError):decision("workflow_dispatch","train",policy=PARENT_POLICY)
