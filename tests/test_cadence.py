from datetime import datetime,timezone
import pytest
from nfl_lab.cadence import decision


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
