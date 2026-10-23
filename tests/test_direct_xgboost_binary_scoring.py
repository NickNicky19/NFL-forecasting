"""New fictional tests for the faithful legacy metadata adapter and guards."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import numpy as np
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import direct_xgboost_binary_scoring as scoring


def fictional():
    query=pd.DataFrame(dict(season=[1999]*4,week=[1]*4,game_id=["toy-game"]*4,
        player_id=["toy-a","toy-b","toy-c","toy-d"],position=["RB","WR","TE","QB"],
        team=["FAKE"]*4,opponent=["DEMO"]*4,kickoff_utc=["1999-01-01T01:00:00Z"]*4,
        cutoff_utc=["1999-01-01T00:00:00Z"]*4))
    donor=query.copy();donor["primary_role"]=[True,True,True,False]
    donor["target"]="anytime_td";donor["method"]="direct_lightgbm_small"
    donor["actual"]=[0.,1.,np.nan,np.nan];donor["participation_state"]=["played","played","DNP","unknown"]
    donor["outcome_state"]=["played_zero","played_nonzero","DNP","unknown"]
    donor["qualified_stats_observed"]=[True,True,False,False]
    return query,donor


class AdapterChecks(unittest.TestCase):
    category=dict(primary_roles=["RB","WR","TE"])
    def test_legacy_both_absent_is_recorded_without_inventing_values(self):
        query,donor=fictional();result,receipt=scoring.cached_labels(query,donor,self.category)
        self.assertNotIn("season_type",result)
        self.assertEqual(receipt["season_type"],"ABSENT_BOTH_FROZEN_LEGACY_PROJECTIONS")
        self.assertFalse(receipt["invented_season_type_values"])

    def test_both_present_must_be_exact(self):
        query,donor=fictional();query["season_type"]="REG";donor["season_type"]="REG"
        _,receipt=scoring.cached_labels(query,donor,self.category)
        self.assertEqual(receipt["season_type"],"PRESENT_BOTH_EXACT")
        donor.loc[0,"season_type"]="POST"
        with self.assertRaises(AssertionError):scoring.cached_labels(query,donor,self.category)

    def test_one_sided_season_type_is_rejected_both_directions(self):
        for side in ("query","donor"):
            query,donor=fictional();(query if side=="query" else donor)["season_type"]="REG"
            with self.assertRaises(ValueError):scoring.cached_labels(query,donor,self.category)

    def test_every_original_context_column_remains_required(self):
        self.assertEqual(len(scoring.CONTEXT),9)
        for column in scoring.CONTEXT:
            query,donor=fictional()
            with self.assertRaises(ValueError):scoring.cached_labels(query.drop(columns=column),donor,self.category)

    def test_context_values_order_dtypes_and_rows_remain_exact(self):
        query,donor=fictional()
        with self.assertRaises(AssertionError):scoring.cached_labels(query,donor.iloc[::-1],self.category)
        donor.loc[0,"team"]="OTHER"
        with self.assertRaises(AssertionError):scoring.cached_labels(query,donor,self.category)
        query,donor=fictional();donor["season"]=donor.season.astype(str)
        with self.assertRaises(AssertionError):scoring.cached_labels(query,donor,self.category)
        with self.assertRaises(ValueError):scoring.cached_labels(query,donor.iloc[:-1],self.category)

    def test_zeros_missing_DNP_unknown_and_qualification_are_preserved(self):
        query,donor=fictional();result,_=scoring.cached_labels(query,donor,self.category)
        pd.testing.assert_series_equal(result.anytime_td,donor.actual,check_names=False)
        pd.testing.assert_series_equal(result.participation_state,donor.participation_state)
        pd.testing.assert_series_equal(result.qualified_stats_observed,donor.qualified_stats_observed)
        self.assertEqual(result.qualified_outcome_state.tolist(),donor.outcome_state.tolist())

    def test_role_and_donor_population_are_not_relaxed(self):
        query,donor=fictional();donor.loc[0,"primary_role"]=False
        with self.assertRaises(ValueError):scoring.cached_labels(query,donor,self.category)
        query,donor=fictional();donor.loc[0,"method"]="filtered-or-other-donor"
        with self.assertRaises(ValueError):scoring.cached_labels(query,donor,self.category)

    def test_input_frames_are_not_mutated(self):
        query,donor=fictional();saved_query=query.copy(deep=True);saved_donor=donor.copy(deep=True)
        scoring.cached_labels(query,donor,self.category)
        pd.testing.assert_frame_equal(query,saved_query);pd.testing.assert_frame_equal(donor,saved_donor)


class GuardChecks(unittest.TestCase):
    def test_unregistered_entry_cannot_open_session(self):
        with patch.object(scoring,"Session",side_effect=AssertionError("session should stay unopened")):
            with self.assertRaises(ValueError):scoring.run({},plan_sha256="0"*64,final_static=lambda:None)

    def test_reused_no_science_scope_forbids_model_load_predict_and_source(self):
        import joblib
        with scoring.no_science():
            with self.assertRaises(AssertionError):joblib.load("fictional-model")
            with self.assertRaises(AssertionError):scoring.parent.direct.DirectBoosterModel.predict(None,None)
            with self.assertRaises(AssertionError):scoring.shared.read_partition(None,None,None)


if __name__=="__main__":unittest.main()
