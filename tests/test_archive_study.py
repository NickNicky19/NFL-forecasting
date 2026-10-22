import copy

import numpy as np
import pandas as pd
import pytest

from nfl_lab.archive_study import archive_population, paired_comparison, prepare_features
from nfl_lab.models import TARGETS


CUTOFF="2026-10-18T10:48:59Z"


def archive_inputs():
    payload={"captured_at":CUTOFF,"forecast_generated_at":"2026-10-18T10:48:52Z","rows":[{"category":"pass_yd","season":2026,"week":6,"player_id":"sid","game_id":"g","team":"A","position":"QB","kickoff":"2026-10-18T13:30:00Z"}]}
    status={"season":{"type":2,"year":2026},"week":{"number":6},"events":[{"id":"g","date":"2026-10-18T13:30:00Z","competitions":[{"competitors":[{"homeAway":"home","team":{"abbreviation":"A"}},{"homeAway":"away","team":{"abbreviation":"B"}}],"status":{"type":{"completed":True}}}]}]}
    identity=pd.DataFrame({"player_id":["00-1234567"],"sleeper_id":["sid"],"identity_status":["source_exact_binding"]})
    schedule=pd.DataFrame({"season":[2026],"week":[6],"game_id":["nfl-g"],"team":["A"],"opponent":["B"],"kickoff_utc":[pd.Timestamp("2026-10-18T13:30:00Z")]})
    return payload,status,identity,schedule


def test_archive_binding_and_unlinked_cold_start_preserve_original_identity():
    payload,status,identity,schedule=archive_inputs()
    cohort,contexts=archive_population(payload,status,identity,schedule,CUTOFF)
    assert cohort.iloc[0].player_id=="sleeper:sid"
    assert contexts.iloc[0].player_id=="00-1234567"
    assert cohort.iloc[0].binding_gap==""
    assert contexts[list(TARGETS)].isna().all().all()
    cold,_=archive_population(payload,status,identity.iloc[:0],schedule,CUTOFF)
    assert cold.iloc[0].canonical_player_id=="sleeper:sid"
    assert cold.iloc[0].identity_binding=="unlinked_or_ambiguous_identity_position_prior"


@pytest.mark.parametrize("change",["late","wrong_team","wrong_kickoff","missing_schedule"])
def test_unsupported_bindings_remain_in_coverage_without_forecasts(change):
    payload,status,identity,schedule=archive_inputs();cutoff=CUTOFF
    if change=="late":cutoff=payload["captured_at"]="2026-10-18T14:00:00Z"
    elif change=="wrong_team":payload["rows"][0]["team"]="C"
    elif change=="wrong_kickoff":payload["rows"][0]["kickoff"]="2026-10-18T13:31:00Z"
    else:schedule=schedule.iloc[:0]
    cohort,contexts=archive_population(payload,status,identity,schedule,cutoff)
    assert len(cohort)==1 and contexts.empty
    assert cohort.iloc[0].binding_gap


def test_duplicate_archive_player_game_target_rejected():
    payload,status,identity,schedule=archive_inputs()
    payload["rows"].append(copy.deepcopy(payload["rows"][0]))
    with pytest.raises(ValueError,match="duplicate archived"):
        archive_population(payload,status,identity,schedule,CUTOFF)


def test_common_features_exclude_unavailable_labels_and_strip_target_outcomes():
    payload,status,identity,schedule=archive_inputs()
    _,contexts=archive_population(payload,status,identity,schedule,CUTOFF)
    contexts["pass_yd"]=999999.;contexts["participation_state"]="played"
    history=[]
    for week,kickoff,yards in [(4,"2026-10-04T13:30:00Z",100.),(5,"2026-10-11T13:30:00Z",99999.)]:
        row={"season":2026,"week":week,"game_id":f"prior-{week}","player_id":"00-1234567","position":"QB","team":"A","opponent":"B","kickoff_utc":pd.Timestamp(kickoff),"outcome_available_utc":pd.Timestamp(kickoff)+pd.Timedelta(days=7),"participation_state":"played","is_home":True}
        row.update({target:0. for target in TARGETS});row["pass_yd"]=yards;row["pass_att"]=20.;row["rec_tgt"]=0.
        history.append(row)
    train,test=prepare_features(pd.DataFrame(history),contexts,CUTOFF)
    assert len(train)==1 and train.iloc[0].week==4
    assert test[list(TARGETS)].isna().all().all()
    assert test.iloc[0].participation_state=="unknown"
    assert test.iloc[0].f_player_pass_yd_mean3==100.
    assert test.iloc[0].f_rest_days==7.


def paired_rows(actual=1.):
    return pd.DataFrame([{"season":2026,"week":6,"game_id":game,"player_id":"sleeper:p","target":"pass_int","actual":actual,"mean":mean,"participation_state":"played","method":method} for game in ["g","h"] for method,mean in [("pinned_website",2.),("lab_selected",1.)]])


def test_matching_actuals_one_week_limits_and_game_uncertainty():
    rows=paired_rows()
    comparison=paired_comparison(rows,"pinned_website","lab_selected")
    assert comparison["paired_rows"]==2 and comparison["games"]==2
    assert comparison["mae_delta"]==-1.
    assert comparison["week_uncertainty"]["interval"] is None
    assert comparison["week_uncertainty"]["weeks"]==1
    assert comparison["descriptive_game_cluster_95pct_interval"]==[-1.,-1.]
    rows.loc[rows.method.eq("lab_selected"),"actual"]=2.
    with pytest.raises(ValueError,match="actual mismatch"):
        paired_comparison(rows,"pinned_website","lab_selected")


def test_missing_rare_counts_are_not_played_zeros():
    missing=paired_comparison(paired_rows(np.nan),"pinned_website","lab_selected")
    zero=paired_comparison(paired_rows(0.),"pinned_website","lab_selected")
    assert missing["paired_rows"]==0
    assert zero["paired_rows"]==2
