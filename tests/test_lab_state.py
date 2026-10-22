from datetime import datetime,timezone,timedelta
import gzip

import pytest

from nfl_lab.state import capture,records,append_outcomes,resolved_outcomes,save,validate_forecast

NOW=datetime(2026,10,22,12,tzinfo=timezone.utc)


def row(**changes):
    return dict(player_id="p",game_id="g",team="A",opponent="B",target="rec",model_id="m",scoring_id="v1",input_sha256="a"*64,code_sha256="b"*64,kickoff_utc=(NOW+timedelta(hours=1)).isoformat(),mean=2,**changes)


def test_restart_and_late_skip(tmp_path):
    assert capture(tmp_path,[row()],lambda:NOW)["recorded"]==1
    assert capture(tmp_path,[row()],lambda:NOW)["duplicates"]==1
    r=row();r["player_id"]="q";r["kickoff_utc"]=NOW.isoformat()
    assert capture(tmp_path,[r],lambda:NOW)["missed"]==1
    assert len([r for b in records(tmp_path,"forecasts") for r in b["rows"]])==1


def test_calculation_crosses_kickoff(tmp_path):
    ticks=iter([NOW,NOW+timedelta(hours=2),NOW+timedelta(hours=2)])
    assert capture(tmp_path,[row()],lambda:next(ticks))["recorded"]==0


def test_tamper_detected(tmp_path):
    capture(tmp_path,[row()],lambda:NOW)
    p=next((tmp_path/"forecasts").glob("*.gz"));p.write_bytes(gzip.compress(b'{}'))
    with pytest.raises(ValueError,match="hash mismatch"):list(records(tmp_path,"forecasts"))


def test_resource_limit_preserves_evidence(tmp_path):
    with pytest.raises(RuntimeError,match="cap reached"):save(tmp_path,"x",{"r":1},max_bytes=0)
    assert not list(tmp_path.rglob("*.gz"))


def observation(value,state="played",**extra):
    return dict(player_id="p",game_id="g",target="rec",actual=value,participation_state=state,source="test",source_sha256=str(value)+state,observed_at=NOW.isoformat(),source_timestamp=None,**extra)


def test_unknown_zero_dnp_distinct_and_retry(tmp_path):
    o=observation(0)
    assert append_outcomes(tmp_path,[o])["appended"]==1
    assert append_outcomes(tmp_path,[o])["appended"]==0
    assert resolved_outcomes(tmp_path)[("p","g","rec")]["actual"]==0
    append_outcomes(tmp_path,[observation(None,"DNP")])
    assert resolved_outcomes(tmp_path)[("p","g","rec")]["state"]=="unresolved_participation_conflict"


def test_unattributed_numeric_change_quarantined(tmp_path):
    append_outcomes(tmp_path,[observation(1),observation(2)])
    assert resolved_outcomes(tmp_path)[("p","g","rec")]["actual"] is None


def test_attributed_numeric_correction_append_only(tmp_path):
    a=observation(1);a["source_timestamp"]="2026-10-22T01:00:00Z"
    b=observation(2);b["source_timestamp"]="2026-10-22T02:00:00Z"
    append_outcomes(tmp_path,[a,b])
    assert resolved_outcomes(tmp_path)[("p","g","rec")]=={"state":"played_corrected","actual":2}
    assert len(list(records(tmp_path,"outcomes")))==2


def test_signed_yards_but_not_negative_counts():
    r=row();r.update(target="rush_yd",mean=-2,issued_at=NOW.isoformat());validate_forecast(r)
    r["target"]="rec"
    with pytest.raises(ValueError,match="negative count"):validate_forecast(r)
