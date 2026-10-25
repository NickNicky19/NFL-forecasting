"""Fictional wrapper checks only; no NFL models, queries, labels or fitting."""
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import direct_xgboost_binary_recovery as recovery


def toy_pair():
    query=pd.DataFrame(dict(season=[2001]*4,week=[1]*4,game_id=["fictional-game"]*4,
        player_id=["fictional-a","fictional-b","fictional-c","fictional-d"],
        team=["FAKE"]*4,opponent=["TOY"]*4,position=["RB","WR","TE","QB"],
        cutoff_utc=["2001-01-01T00:00:00Z"]*4,kickoff_utc=["2001-01-01T01:00:00Z"]*4,
        season_type=["REG"]*4))
    donor=query.copy();donor["primary_role"]=[True,True,True,False]
    donor["target"]="anytime_td";donor["method"]="direct_lightgbm_small"
    donor["actual"]=[0.,1.,np.nan,np.nan]
    donor["participation_state"]=["played","played","DNP","unknown"]
    donor["outcome_state"]=["played_zero","played_nonzero","DNP","unknown"]
    return query,donor


class SequenceChecks(unittest.TestCase):
    def test_later_model_is_blocked_until_earlier_cells_freeze(self):
        state=recovery.Sequence()
        with self.assertRaises(ValueError):state.before_model(2023,"small")
        state.reserve(2022,"small",8624)
        with self.assertRaises(ValueError):state.before_model(2022,"medium")
        state.freeze(2022,"small",8624);state.before_model(2022,"medium")

    def test_labels_are_blocked_until_all_six_forecasts_freeze(self):
        state=recovery.Sequence()
        with self.assertRaises(ValueError):state.before_labels()
        for year,level in recovery.CELLS:
            state.reserve(year,level,8624);state.freeze(year,level,8624)
            with self.assertRaises(ValueError):state.before_labels()
        state.global_freeze();state.before_labels();self.assertEqual(state.rows,51744)

    def test_rows_are_charged_before_inference_and_not_refunded(self):
        state=recovery.Sequence();state.reserve(2022,"small",123)
        self.assertEqual(state.rows,123)
        with self.assertRaises(ValueError):state.reserve(2022,"small",123)
        with self.assertRaises(ValueError):state.freeze(2022,"small",124)
        self.assertEqual(state.rows,123)

    def test_no_silent_row_budget_expansion_or_unregistered_cell(self):
        state=recovery.Sequence()
        with self.assertRaises(ValueError):state.reserve(2022,"small",60001)
        self.assertEqual(state.rows,0)
        with self.assertRaises(ValueError):state.before_model(2022,"large")
        with self.assertRaises(ValueError):state.global_freeze()


class DonorChecks(unittest.TestCase):
    category=dict(primary_roles=["RB","WR","TE"])
    def test_known_zero_DNP_unknown_and_missing_stay_distinct(self):
        query,donor=toy_pair();result=recovery.donor_labels(query,donor,self.category)
        pd.testing.assert_series_equal(result.anytime_td,donor.actual,check_names=False)
        self.assertEqual(result.qualified_outcome_state.tolist(),donor.outcome_state.tolist())
        self.assertEqual(result.participation_state.tolist(),["played","played","DNP","unknown"])

    def test_order_changes_are_rejected(self):
        query,donor=toy_pair()
        with self.assertRaises(AssertionError):recovery.donor_labels(query,donor.iloc[::-1],self.category)

    def test_context_changes_are_rejected(self):
        query,donor=toy_pair();donor.loc[0,"cutoff_utc"]="2001-01-01T00:10:00Z"
        with self.assertRaises(AssertionError):recovery.donor_labels(query,donor,self.category)

    def test_role_changes_are_rejected(self):
        query,donor=toy_pair();donor.loc[0,"primary_role"]=False
        with self.assertRaises(ValueError):recovery.donor_labels(query,donor,self.category)

    def test_wrong_donor_or_changed_participation_is_rejected(self):
        query,donor=toy_pair();donor.loc[0,"method"]="favorable-filtered-donor"
        with self.assertRaises(ValueError):recovery.donor_labels(query,donor,self.category)
        donor.loc[0,"method"]="direct_lightgbm_small";donor.loc[0,"participation_state"]="imputed-zero"
        with self.assertRaises(ValueError):recovery.donor_labels(query,donor,self.category)

    def test_missing_context_is_not_invented(self):
        query,donor=toy_pair()
        with self.assertRaises(ValueError):recovery.donor_labels(query,donor.drop(columns="season_type"),self.category)


class BoundaryChecks(unittest.TestCase):
    def test_original_source_and_training_routes_are_disabled(self):
        with recovery.no_fits_or_sources():
            with self.assertRaises(AssertionError):recovery.shared.read_partition(None,None,None)
            with self.assertRaises(AssertionError):recovery.parent.direct.DirectBoosterModel.fit()

    def test_thread_controller_libc_resolution_is_process_free(self):
        libc={Path(line.split()[-1]).resolve() for line in Path("/proc/self/maps").read_text().splitlines()
            if len(line.split())>=6 and line.split()[-1].endswith("/libc.so.6")}
        self.assertEqual(len(libc),1)
        path=next(iter(libc));binding=dict(path=str(path),sha256=recovery.shared.sha(path))
        with recovery.process_free_threads(binding):
            self.assertEqual(recovery.threadpoolctl.find_library("c"),str(path))
            with self.assertRaises(AssertionError):recovery.threadpoolctl.find_library("other")
            with recovery.threadpool_limits(limits=2):pass

    def test_unregistered_direct_entry_is_rejected(self):
        with self.assertRaises(ValueError):recovery.run({},plan_sha256="0"*64,final_static=lambda:None)

    def test_retained_original_content_is_reused_and_new_body_limit_is_prewrite(self):
        with tempfile.TemporaryDirectory(prefix="fictional-binary-wrapper-") as folder:
            root=Path(folder);blob=root/"cas";blob.mkdir();output=root/"new";output.mkdir()
            original=b"fictional-old-content";digest=hashlib.sha256(original).hexdigest()
            (blob/digest).write_bytes(original)
            class FakeStore:
                def __init__(self,*a,**k):self.blob_root=blob;self.writes=0
                def register_root(self,path):return output
                def write_bytes(self,path,body,*,replace=False):
                    self.writes+=1;body=bytes(body);name=hashlib.sha256(body).hexdigest()
                    if not (blob/name).exists():(blob/name).write_bytes(body)
                    os.link(blob/name,path);return len(body)
            policy=root/"fictional-policy.json";policy.write_text("{}")
            with patch.object(recovery,"OperationalStorage",FakeStore),patch.object(recovery.shared,"_spec",return_value=policy):
                store,_=recovery.storage(dict(cache="fictional",source_policy={},output=str(output)))
                store.write_bytes(output/"old-alias",original)
                self.assertEqual(store.report_retention()["charged_bytes"],0)
                with self.assertRaises(RuntimeError):store.write_bytes(output/"too-big",bytes(16777217))
                self.assertEqual(store.writes,1);self.assertFalse((output/"too-big").exists())


if __name__=="__main__":unittest.main()
