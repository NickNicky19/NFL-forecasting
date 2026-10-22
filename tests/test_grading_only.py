import pytest

from nfl_lab import live
from nfl_lab.state import records


@pytest.mark.parametrize("source_available",[True,False])
def test_grading_only_has_no_pregame_capture_path(tmp_path,monkeypatch,source_available):
    def fetch(*args):
        if not source_available:raise RuntimeError("source unavailable")
        return {"s1":{"gsis_id":"00-1"}},{}
    def never_capture(*args,**kwargs):raise AssertionError("grading must not capture a forecast")
    monkeypatch.setattr(live,"fetch",fetch)
    monkeypatch.setattr(live,"capture",never_capture)
    monkeypatch.setattr(live,"grade_saved",lambda state,cache,players:{"appended":0,"pending_outcomes":1})
    result=live.grade_only(tmp_path/"state",tmp_path/"data")
    assert result["state"]=="GRADING_ONLY_NO_PREGAME_ISSUANCE"
    assert result["grading"]["pending_outcomes"]==1
    assert bool(result["player_source_limit"]) is (not source_available)
    assert list(records(tmp_path/"state","forecasts"))==[]
