"""Initial remaining-slate metadata only; no source/model/forecast execution."""
from contextlib import contextmanager
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from nfl_lab import weekly_generic_producer as g, weekly_initial_remaining_v1 as initial
from nfl_lab.state import utc

NOW=utc("2026-10-24T11:00:00Z")


def registration():
    return dict(schema_version=initial.REGISTRATION,registration_id=initial.REGISTRATION_ID,state="FROZEN_ROOT_REGISTERED",
        registered_at_utc="2026-10-24T10:00:00Z",season=2026,week=7,season_type="REG",slate_id=initial.REGISTRATION_ID,
        slate_kind="INITIAL_REMAINING_ONE_TIME",full_week_first_kickoff_utc=initial.FULL_FIRST,
        first_remaining_kickoff_utc=initial.REMAINING_FIRST,elapsed_game_ids=list(initial.ELAPSED),remaining_game_ids=list(initial.REMAINING),
        elapsed_game_count=1,remaining_game_count=13,input_cutoff_utc=initial.CUTOFF,maximum_uses=1,
        build_kind="GENUINE_HOSTED_FIXED_BUILD_V1",startup_policy_sha256="0ee3eccf4f0e9ed85ee46c6ba4f6df404459fb4f3cabba469bf6dffd9ee2456c")


def schedule():
    # Registered public game IDs; synthetic metadata-only later kickoff times.
    return [dict(season=2026,week=7,game_type="REG",game_id=initial.ELAPSED[0],kickoff_utc=initial.FULL_FIRST)]+[
        dict(season=2026,week=7,game_type="REG",game_id=game,kickoff_utc=initial.REMAINING_FIRST) for game in initial.REMAINING]


class InitialRemainingChecks(unittest.TestCase):
    def test_routine_full_week_deadline_stays_past_initial_is_explicit_partial(self):
        r=registration();ref={"path":"/fictional/registration.json","bytes":1,"sha256":"a"*64}
        partial=initial.prepare_initial_slate(schedule(),r,ref,now=NOW)
        whole=g.prepare_slate(schedule(),season=2026,week=7,game_cutoffs={i:initial.CUTOFF for i in initial.REMAINING},now=NOW)
        self.assertLess(utc(whole["weekly_deadline_utc"]),NOW)
        self.assertGreater(utc(partial["weekly_deadline_utc"]),NOW)
        self.assertEqual((partial["scheduled_games"],partial["elapsed_games"]),(14,1))
        self.assertEqual(partial["scheduled_first_kickoff_utc"],initial.REMAINING_FIRST)
        self.assertEqual(partial["schedule_identity_sha256"],whole["schedule_identity_sha256"])
        self.assertEqual(partial["slate_contract"]["full_week_first_kickoff_utc"],initial.FULL_FIRST)
        self.assertNotEqual(partial,whole)

    def test_registration_is_closed_one_time_not_old12Z_or_future_choice(self):
        initial.validate_registration(registration(),now=NOW)
        for field,value in [("registered_at_utc",None),("registered_at_utc","2026-10-24T14:00:00Z"),
            ("maximum_uses",2),("input_cutoff_utc","2026-10-24T12:00:00Z"),("elapsed_game_count",0),("state","PREPARED")]:
            r=registration();r[field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):initial.validate_registration(r,now=NOW)
        r=registration();r["unknown_override"]=True
        with self.assertRaisesRegex(ValueError,"closed"):initial.validate_registration(r,now=NOW)
        with self.assertRaisesRegex(ValueError,"registration/choice"):initial.validate_registration(registration(),now=utc(initial.CUTOFF))

    def test_exact_fourteen_census_never_shrinks_or_invents_elapsed(self):
        ref={"sha256":"a"*64};r=registration()
        for rows in [schedule()[:-1],schedule()+[schedule()[0]],schedule()[1:]]:
            with self.assertRaises(ValueError):initial.prepare_initial_slate(rows,r,ref,now=NOW)
        rows=schedule();rows[1]["kickoff_utc"]="2026-10-24T10:00:00Z"
        with self.assertRaisesRegex(ValueError,"elapsed/remaining"):initial.prepare_initial_slate(rows,r,ref,now=NOW)

    def test_new_build_and_current_receipts_must_follow_actual_registration(self):
        r=registration()
        models=[dict(category={"target":t},method_id=m,artifact_created_at="2026-10-24T10:40:00Z",
            fit_receipt=dict(training_source_capture_completed_at="2026-10-24T10:10:00Z",training_started_at="2026-10-24T10:20:00Z",training_completed_at="2026-10-24T10:30:00Z")) for t,m in sorted(initial.EXPECTED)]
        receipts={n:dict(status="acquired",retrieved_utc="2026-10-24T10:05:00Z") for n in ("schedules.csv.receipt.json","roster_weekly_2026.parquet.receipt.json","stats_player_week_2026.parquet.receipt.json")}
        initial.validate_fresh_initial_metadata(r,models,receipts,now=NOW)
        old=deepcopy(models);old[0]["fit_receipt"]["training_started_at"]="2026-10-24T09:00:00Z"
        with self.assertRaisesRegex(ValueError,"follow registration"):initial.validate_fresh_initial_metadata(r,old,receipts,now=NOW)
        old=deepcopy(receipts);old["schedules.csv.receipt.json"]["retrieved_utc"]="2026-10-24T09:00:00Z"
        with self.assertRaisesRegex(ValueError,"follow registration"):initial.validate_fresh_initial_metadata(r,models,old,now=NOW)

    def test_one_time_journal_prevents_different_output_namespace_retry(self):
        class Store:
            @contextmanager
            def transaction(self):yield
            def register_root(self,p):Path(p).mkdir(parents=True,exist_ok=True)
            def atomic_json(self,p,x):
                with Path(p).open("x") as f:json.dump(x,f)
        with tempfile.TemporaryDirectory() as d:
            b=object.__new__(initial.InitialRemainingBackend);b.plan={"cache":d,"output_root":"/fictional/first"};b.clock=lambda:NOW;b.store=Store()
            b.consume_registration(registration(),{"sha256":"a"*64})
            b.plan["output_root"]="/fictional/different"
            with self.assertRaisesRegex(ValueError,"already consumed"):b.consume_registration(registration(),{"sha256":"b"*64})

    def test_explicit_initial_backend_dispatch_is_registered_not_general_injection(self):
        p={"fictional":"metadata"};b=object.__new__(initial.InitialRemainingBackend);b.plan=p
        with patch.object(g,"validate_plan"),patch.object(initial.InitialRemainingBackend,"run",return_value={"fictional_only":True}) as run:
            self.assertEqual(g.execute(p,backend=b),{"fictional_only":True});self.assertEqual(run.call_count,1)
            other=dict(p)
            with self.assertRaisesRegex(ValueError,"explicitly registered"):g.execute(other,backend=b)

    def test_typed_registration_and_adapter_hash_bind_selected_procedure(self):
        s=initial.prepare_initial_slate(schedule(),registration(),{"sha256":"a"*64},now=NOW)
        selection={"members":[],"decision":{"slate_contract":s["slate_contract"]}}
        codes={"nfl_lab/weekly_generic_producer.py":"g"*64,"nfl_lab/weekly_adaptive.py":"s"*64,"nfl_lab/weekly_initial_remaining_v1.py":"a"*64}
        first=g.selected_procedure(selection,codes);codes["nfl_lab/weekly_initial_remaining_v1.py"]="b"*64
        self.assertNotEqual(first,g.selected_procedure(selection,codes))
        selection["decision"].pop("slate_contract")
        first=g.selected_procedure(selection,codes);codes["nfl_lab/weekly_initial_remaining_v1.py"]="c"*64
        self.assertEqual(first,g.selected_procedure(selection,codes))


if __name__=="__main__":unittest.main()
