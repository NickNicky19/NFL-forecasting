import copy
import importlib.util
import json
from pathlib import Path

import jsonschema
import pytest

from nfl_lab.scoring import PPR_COMPONENTS,ppr_points


def test_schema_signed_yards_missing_identity_and_event_support():
    schema=json.loads(Path('schemas/forecast-v1.json').read_text())
    row={"player_id":"00-1","sleeper_id":"1","game_id":"espn:1","team":"A","opponent":"B","target":"rush_yd","period":"full_game","model_id":"m","scoring_id":"nfl-full-game-v1","model_config_sha256":"a"*64,"input_sha256":"b"*64,"code_sha256":"c"*64,"kickoff_utc":"2026-10-23T00:15:00Z","issued_at":"2026-10-22T12:00:00Z","mean":-2.5,"fallback":None,"prediction_functional":"conditional_played_mean"}
    jsonschema.validate(row,schema)
    bad=copy.copy(row);bad["target"]="rec"
    with pytest.raises(jsonschema.ValidationError):jsonschema.validate(bad,schema)
    bad=copy.copy(row);bad.pop("sleeper_id")
    with pytest.raises(jsonschema.ValidationError):jsonschema.validate(bad,schema)
    bad=copy.copy(row);bad.update(target="anytime_td",mean=1.01)
    with pytest.raises(jsonschema.ValidationError):jsonschema.validate(bad,schema)


def test_exact_pinned_consumer_arithmetic_fixture():
    # Synthetic permitted consumer fixture: signed/fractional yards and rare
    # components exercise the pinned site's unchanged arithmetic and exception.
    s={k:0 for k in PPR_COMPONENTS};s.update(pass_yd=101.25,pass_int=1,rush_yd=-3,rec=2,rec_yd=12.5,fum_lost=1,st_ff=1,fum_rec_td=1,idp_fum_rec=1)
    expected=round(101.25*.04-1-.3+2+1.25-2+1,2)
    assert ppr_points(s)==expected
    s["st_td"]=None
    assert ppr_points(s) is None
