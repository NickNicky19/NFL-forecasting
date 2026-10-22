from datetime import datetime,timezone,timedelta

from nfl_lab.state import capture,save,append_outcomes
from nfl_lab.prospective import score_saved

NOW=datetime(2026,10,22,12,tzinfo=timezone.utc)


def forecast():
    return dict(player_id="p",game_id="g",team="A",opponent="B",season=2026,week=7,position="WR",target="rec",model_id="recent",scoring_id="v1",input_sha256="a"*64,code_sha256="b"*64,kickoff_utc=(NOW+timedelta(hours=1)).isoformat(),mean=2,scale=2,family="negbin",fallback="",p_participation=.8,code_integrity="pre_post_source_digest_required")


def test_remote_publication_gate_and_actual_saved_grading(tmp_path):
    result=capture(tmp_path,[forecast()],lambda:NOW)
    assert score_saved(tmp_path)["forecast_counts"]["local_only"]==1
    save(tmp_path,"publication",dict(batch=result["batch"],commit="c"*40,observed_remote_readback_at=NOW.isoformat(),timely_rows=1,late_rows=0))
    assert score_saved(tmp_path)["forecast_counts"]["pending"]==1
    append_outcomes(tmp_path,[dict(player_id="p",game_id="g",target="rec",actual=1,participation_state="played",source="test",source_sha256="d"*64,observed_at=(NOW+timedelta(days=1)).isoformat(),source_timestamp=None)])
    scores=score_saved(tmp_path)
    assert scores["categories"][0]["mae"]==1
    assert scores["categories"][0]["scored_rows"]==1


def test_late_completion_or_publication_never_scored(tmp_path):
    r=capture(tmp_path,[forecast()],lambda:NOW)
    save(tmp_path,"publication",dict(batch=r["batch"],commit="c"*40,observed_remote_readback_at=(NOW+timedelta(hours=2)).isoformat(),timely_rows=0,late_rows=1))
    assert score_saved(tmp_path)["forecast_counts"]["late"]==1
    assert score_saved(tmp_path)["categories"]==[]
