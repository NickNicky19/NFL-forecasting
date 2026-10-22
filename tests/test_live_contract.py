import copy
from datetime import datetime,timezone

import pytest

from nfl_lab.live import schedule_games,future_population


def board():
    return {"season":{"type":2},"events":[{"id":"1","date":"2026-10-23T00:15:00Z","competitions":[{"competitors":[{"homeAway":"home","team":{"abbreviation":"WSH"}},{"homeAway":"away","team":{"abbreviation":"NYG"}}],"status":{"type":{"completed":False,"name":"STATUS_SCHEDULED"}}}]}]}


def test_schedule_schema_and_identity():
    b=board();g=schedule_games(b)
    assert g[0]["game_id"]=="espn:1" and g[0]["home"]=="WAS"
    b["events"]*=2
    with pytest.raises(ValueError,match="duplicate"):schedule_games(b)
    b=board();b["season"]["type"]=3
    with pytest.raises(ValueError,match="regular-season"):schedule_games(b)


def test_sparse_unlinked_player_never_disappears_or_name_matches():
    players={"1":{"position":"QB","team":"WAS","active":True,"gsis_id":None,"full_name":"New QB"},"2":{"position":"WR","team":"NYG","active":True,"gsis_id":"00-1"},"3":{"position":"WR","team":"NYG","active":False}}
    p=future_population(players,schedule_games(board()),2026,7)
    assert set(p.player_id)=={"sleeper:1","00-1"}
    assert set(p.participation_state)=={"unknown"}
