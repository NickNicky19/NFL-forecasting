"""New fictional grading checks; no actual source/model/forecast execution."""
from copy import deepcopy
from datetime import timedelta
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from nfl_lab import live,state,weekly_grading as w

ROOT=Path(__file__).resolve().parents[1]
NOW=state.utc("2026-10-24T11:00:00Z")
KICK="2026-10-18T17:00:00Z"


def fixture():
    query=dict(season=2026,week=6,game_id="fictional-gsis-game",player_id="00-0000001",sleeper_id="123",position="RB",team="A",opponent="B",kickoff_utc=KICK,cutoff_utc="2026-10-18T16:00:00Z")
    b=dict(gsis_game_id=query["game_id"],gsis_id=query["player_id"],sleeper_id="123",website_player_id="123",website_game_id="999",team="A",opponent="B",kickoff_utc=KICK,
        query_source_sha256="a"*64,schedule_source_sha256="b"*64,actual_visible_board_compatibility="NOT_YET_CHECKED")
    b["identity_binding_sha256"]=state.digest(b)
    roles={t:dict(modeled_roles=["RB"],primary_roles=["RB"]) for t in sorted(w.TARGETS)}
    return query,{"identities":[b]},roles


def board(final=True):
    return dict(season={"type":2,"year":2026},week={"number":6},events=[dict(id="999",date=KICK,competitions=[dict(competitors=[
        dict(homeAway="home",team={"abbreviation":"A"}),dict(homeAway="away",team={"abbreviation":"B"})],status={"type":{"completed":final,"name":"STATUS_FINAL"}})])])


def fetcher(stats,final=True):
    receipt={"sha256":"c"*64,"retrieved_utc":"2026-10-24T10:00:00Z"}
    def fetch(cache,name,url):
        if name.startswith("grade-schedule"):return board(final),receipt
        return {"123":{"stats":stats,"team":"A","season":2026,"week":6}},receipt
    return fetch


def stream(name="initial-manual-15z"):
    return dict(schema_version=w.VERSION+"-stream",stream_id=name,stream_kind="initial_manual",horizon_version="initial-15Z-v1")


def decision():
    return dict(category="rec",season=2026,week=6,slate_id="fictional-slate",horizon="player_game",evidence_lane="original_pregame",
        weekly_decision_cutoff_utc="2026-10-17T10:00:00Z",slate_first_kickoff_utc=KICK)


class WeeklyGradingChecks(unittest.TestCase):
    def test_policy_hash_matches_supplied_and_actual_active_scope_before_inputs(self):
        from types import SimpleNamespace
        from nfl_lab.operational_sources import load_source_policy
        import resource
        policy_path=ROOT/"config/operational-source-policy-v2.json";policy=load_source_policy(policy_path)
        active=SimpleNamespace(weekly_grading_policy=dict(policy))
        self.assertEqual(w.validate_grading_policy({"source_policy_sha256":policy["_policy_sha256"]},policy_path,active)["_policy_sha256"],policy["_policy_sha256"])
        bad=SimpleNamespace(weekly_grading_policy={**policy,"_policy_sha256":"f"*64})
        with self.assertRaisesRegex(ValueError,"mismatch"):w.validate_grading_policy({"source_policy_sha256":policy["_policy_sha256"]},policy_path,bad)
        with self.assertRaisesRegex(ValueError,"SHA256 required"):w.validate_grading_policy({},policy_path,active)
        with tempfile.TemporaryDirectory() as d:
            changed=Path(d)/"same-body-different-physical-policy.json";changed.write_bytes(policy_path.read_bytes()+b'\n')
            with self.assertRaisesRegex(ValueError,"mismatch"):w.validate_grading_policy({"source_policy_sha256":policy["_policy_sha256"]},changed,active)
            plan=json.loads((ROOT/"config/weekly-grading-v1.json").read_text());plan.update(state="FROZEN_ROOT_REVIEWER_SEALED",execution_authorized=True,
                review={"status":"PREEXEC_PASS","integrator":"/root"},source_policy_sha256="f"*64)
            p=Path(d)/"mismatch-plan.json";p.write_text(json.dumps(plan))
            with patch("nfl_lab.operational_io.active_storage",return_value=active),patch.object(resource,"setrlimit",side_effect=AssertionError("resource mutation before policy")),\
                patch("nfl_lab.owned_reference_batch.validate_owned_references",side_effect=AssertionError("input decode before policy")),patch.object(live,"fetch",side_effect=AssertionError("source call")):
                with self.assertRaisesRegex(ValueError,"mismatch"):w.grade_from_plan(p,w.binding(p)["sha256"],Path(d)/"state",Path(d)/"cache",source_policy=policy_path)

    def test_exact_initial_decision_adapter_retains_original_hash_clocks_and_lineage(self):
        from nfl_lab import weekly_private_selected as selected
        policy=json.loads((ROOT/"config/weekly-provisional-live-policy-v1.json").read_text())
        ref=lambda name:{"path":"/fictional/"+name,"bytes":1,"sha256":state.digest(name)}
        policy_ref=ref("policy.json");capture_ref=ref("capture.json");bridge_ref=ref("bridge.json");decision_ref=ref("decision.json")
        categories={};slots={};roles={}
        for target,method in selected.CHOICES.items():
            support="bernoulli" if target=="anytime_td" else "count" if target in w.COUNTS else "signed_integer"
            methods=("LAB_CDF","CATBOOST_MEDIUM") if method=="TD_EQUAL_CDF_CAT" else (method,)
            categories[target]=dict(primary_roles=["RB"],support=support,product={"count":"point_mean","signed_integer":"point_median","bernoulli":"binary_probability"}[support],methods={})
            roles[target]=dict(modeled_roles=["RB"],primary_roles=["RB"])
            for m in methods:
                categories[target]["methods"][m]=dict(model_version=state.digest(target+m),procedure_version=state.digest(m))
                slots[target,m]=dict(persistence={"binding":ref(target+m),"completed_at":"2026-10-24T09:34:00Z"},projection=ref("projection"))
        choice="2026-10-24T09:32:23.962533+00:00"
        choices=selected.decision(policy,{"categories":categories},slots,policy_ref=policy_ref,capture_ref=capture_ref,bridge_ref=bridge_ref,
            materialization_started_at="2026-10-24T10:00:00Z",startup_choice_at=choice,source_capture_at="2026-10-24T09:08:00Z",code_pins_sha256="a"*64)
        freeze=dict(schema_version="weekly-current-inference-capture-v1",startup_policy=policy_ref,startup_policy_registered_at=policy["registered_at_utc"],
            weekly_decision_cutoff_utc=choice,actual_completed_at="2026-10-24T09:35:00Z",input_cutoff_utc=selected.CUTOFF)
        queries=[dict(season=2026,week=7,cutoff_utc=selected.CUTOFF,kickoff_utc="2026-10-25T13:30:00Z")]
        kwargs=dict(decision_ref=decision_ref,freeze_ref=capture_ref,bridge_ref=bridge_ref)
        result=w.grading_decisions(choices,freeze,queries,roles,**kwargs)
        self.assertEqual(len(result),11)
        for row in result:
            self.assertEqual(row["original_decision_sha256"],state.digest(choices));self.assertEqual(row["original_decision_binding"],decision_ref)
            self.assertEqual(row["weekly_decision_cutoff_utc"],choice);self.assertEqual(row["horizon"],"player_game");self.assertEqual(row["slate_id"],selected.SLATE)
            self.assertEqual(row["original_selected_members"],choices["categories"][row["category"]]["members"])
            self.assertEqual(row["original_startup_policy_registered_at"],choices["startup_policy_registered_at"])
            self.assertEqual(row["original_shared_feature_persist_completed_at"],choices["shared_feature_persist_completed_at"])
            self.assertEqual(row["original_input_cutoff_utc"],selected.CUTOFF)
        broken=deepcopy(choices);broken["startup_choice_at"]="2026-10-24T09:31:00Z"
        with self.assertRaisesRegex(ValueError,"choice clocks"):w.grading_decisions(broken,freeze,queries,roles,**kwargs)
        with self.assertRaisesRegex(ValueError,"unsupported"):w.grading_decisions({"schema_version":"unknown","selections":[]},freeze,queries,roles,**kwargs)

    def test_generic_decision_format_requires_its_own_terminal_binding(self):
        ref={"sha256":"a"*64};choices={"schema_version":"weekly-generic-future-producer-v1-weekly-choice","selections":[{"decision":decision()}]}
        freeze={"schema_version":"weekly-generic-future-producer-v1","decision":ref}
        kwargs=dict(decision_ref=ref,freeze_ref={},bridge_ref={})
        self.assertEqual(w.grading_decisions(choices,freeze,[],{},**kwargs),[decision()])
        freeze["decision"]={"sha256":"b"*64}
        with self.assertRaisesRegex(ValueError,"binding differs"):w.grading_decisions(choices,freeze,[],{},**kwargs)

    def test_metadata_offers_do_not_depend_on_points_or_roster_status(self):
        q,b,r=fixture()
        class Poison:
            def __float__(self):raise AssertionError("forecast read")
        q.update(forecast_value=Poison(),actual=Poison(),roster_status="INA")
        rows=w.opportunity_rows([q],b,r)
        self.assertEqual(len(rows),11);self.assertTrue(all("forecast_value" not in x and "actual" not in x for x in rows))
        self.assertEqual({x["target"] for x in rows},w.TARGETS)
        r["fantasy_ppr"]={"modeled_roles":["RB"],"primary_roles":["RB"]}
        with self.assertRaisesRegex(ValueError,"eleven"):w.opportunity_rows([q],b,r)

    def test_identity_digest_and_conflicts_fail_before_collection(self):
        q,b,r=fixture();b["identities"][0]["sleeper_id"]="456"
        with self.assertRaisesRegex(ValueError,"bridge digest"):w.opportunity_rows([q],b,r)
        q,b,r=fixture()
        with self.assertRaisesRegex(ValueError,"duplicate original"):w.opportunity_rows([q,q],b,r)
        rows=w.opportunity_rows([q],b,r);rows[0]["original_game_id"]="wrong"
        with self.assertRaisesRegex(ValueError,"offered identity"):w.validate_collector_rows(rows)

    def test_default_records_and_optin_metadata_use_identical_live_collector(self):
        q,b,r=fixture();rows=w.opportunity_rows([q],b,r)
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);old=root/"old";new=root/"new"
            state.save(old,"forecasts",{"rows":rows})  # Legacy-only fictional parity fixture.
            with patch.object(live,"fetch",side_effect=fetcher({"gp":1,"rec":0,"rush_yd":-2,"rush_td":0,"rec_td":0})),\
                patch.object(live,"now_utc",return_value=NOW),patch("nfl_lab.grading_sources.load_cached_grading_context",side_effect=ValueError("fictional supplement unavailable")):
                a=live._grade_saved(old,root/"cache",{});c=live._grade_saved(new,root/"cache",{},opportunity_rows=rows)
            c.pop("weekly_finality")
            self.assertEqual(a,c);self.assertEqual(state.resolved_outcomes(old),state.resolved_outcomes(new))
            self.assertEqual(list(state.records(new,"forecasts")),[])
            self.assertEqual(state.resolved_outcomes(new)[(q["player_id"],"espn:999","rec")]["actual"],0)
            self.assertEqual(state.resolved_outcomes(new)[(q["player_id"],"espn:999","rush_yd")]["actual"],-2)

    def test_fractional_counts_missing_and_roster_nonappearance_are_not_zero(self):
        q,b,r=fixture();rows=[x for x in w.opportunity_rows([q],b,r) if x["target"]=="rec"]
        with tempfile.TemporaryDirectory() as d:
            for index,stats in enumerate([{"gp":1,"rec":1.5},{"gp":1},{"rec":0}]):
                dest=Path(d)/str(index)
                with patch.object(live,"fetch",side_effect=fetcher(stats)),patch.object(live,"now_utc",return_value=NOW),\
                    patch("nfl_lab.grading_sources.load_cached_grading_context",side_effect=ValueError("fixture")):
                    live._grade_saved(dest,Path(d)/"cache",{},opportunity_rows=rows)
                actual=state.resolved_outcomes(dest)[(q["player_id"],"espn:999","rec")]
                self.assertIsNone(actual["actual"]);self.assertEqual(actual["state"],"played" if stats.get("gp")==1 else "unknown")

    def test_append_only_revisions_use_actual_new_clock_and_quarantine_unknown_correction(self):
        q,b,r=fixture();row=next(x for x in w.opportunity_rows([q],b,r) if x["target"]=="rec")
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);obs=dict(player_id=q["player_id"],game_id="espn:999",target="rec",actual=0,participation_state="played",source="fictional",source_sha256="d"*64,status_sha256="e"*64,observed_at="2026-10-23T10:00:00Z",source_timestamp=None)
            state.append_outcomes(root/"collector",[obs]);first,n=w.append_resolved(root,stream(),[row],clock=lambda:NOW)
            self.assertEqual(n,1);self.assertEqual(first[0]["actual"],0);self.assertEqual(first[0]["available_at"],NOW.isoformat())
            same,n=w.append_resolved(root,stream(),[row],clock=lambda:NOW+timedelta(hours=1))
            self.assertEqual(n,0);self.assertEqual(same,first)
            state.append_outcomes(root/"collector",[{**obs,"actual":2,"source_sha256":"f"*64}])
            changed,n=w.append_resolved(root,stream(),[row],clock=lambda:NOW+timedelta(hours=2))
            self.assertEqual(n,1);self.assertEqual(changed[0]["revision"],2);self.assertIsNone(changed[0]["actual"])
            self.assertEqual(changed[0]["resolution_state"],"unresolved_numeric_conflict")
            self.assertEqual(len(list(state.records(root,"weekly_versions"))),2)

    def test_known_clock_correction_and_DNP_use_unchanged_resolver(self):
        q,b,r=fixture();row=next(x for x in w.opportunity_rows([q],b,r) if x["target"]=="rec")
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);base=dict(player_id=q["player_id"],game_id="espn:999",target="rec",participation_state="played",source="same-published-origin",source_sha256="a"*64,observed_at=NOW.isoformat())
            state.append_outcomes(root/"collector",[{**base,"actual":1,"source_timestamp":"2026-10-23T01:00:00Z"},{**base,"actual":2,"source_timestamp":"2026-10-23T02:00:00Z"}])
            outcomes,_=w.append_resolved(root,stream(),[row],clock=lambda:NOW)
            self.assertEqual(outcomes[0]["actual"],2);self.assertEqual(outcomes[0]["resolution_state"],"played_corrected")
            root=Path(d)/"DNP";state.append_outcomes(root/"collector",[{**base,"actual":None,"participation_state":"DNP","source_timestamp":None}])
            outcomes,_=w.append_resolved(root,stream(),[row],clock=lambda:NOW)
            self.assertEqual(outcomes[0]["participation_state"],"DNP");self.assertIsNone(outcomes[0]["actual"])

    def test_identity_quarantine_withdraws_numeric_result_without_new_zero(self):
        q,b,r=fixture();row=next(x for x in w.opportunity_rows([q],b,r) if x["target"]=="rec")
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);base=dict(player_id=q["player_id"],game_id="espn:999",target="rec",participation_state="played",source="fixture",source_sha256="a"*64,observed_at=NOW.isoformat(),source_timestamp=None,actual=2)
            state.append_outcomes(root/"collector",[base]);w.append_resolved(root,stream(),[row],clock=lambda:NOW)
            state.append_outcomes(root/"collector",[{**base,"actual":None,"participation_state":"unknown","identity_quarantined":True}])
            rows,n=w.append_resolved(root,stream(),[row],clock=lambda:NOW+timedelta(minutes=1))
            self.assertEqual(n,1);self.assertEqual(rows[0]["outcome_state"],"unresolved_identity_conflict")
            self.assertEqual(rows[0]["participation_state"],"unknown");self.assertIsNone(rows[0]["actual"])

    def test_whole_week_gate_requires_every_actual_scheduled_game(self):
        games=[dict(game_id="espn:999",kickoff_utc=KICK,home="A",away="B",final=True)]
        frozen=[dict(season=2026,week=6,website_game_id=x,kickoff_utc=KICK,home="A",away="B") for x in ("999","1000")]
        proof=dict(season=2026,week=6,games=games,status_source_sha256="a"*64,observed_at="2026-10-24T10:00:00Z")
        ready,pending=w.complete_weeks([proof],frozen,[decision()],grade_completed_at=NOW.isoformat())
        self.assertFalse(ready);self.assertEqual(len(pending),1)
        proof["games"].append({**games[0],"game_id":"espn:1000"})
        ready,pending=w.complete_weeks([proof],frozen,[decision()],grade_completed_at=NOW.isoformat())
        self.assertEqual(len(ready),1);self.assertFalse(pending);self.assertEqual(ready[0]["grade_completed_at"],NOW.isoformat())
        proof["games"][1]["final"]=False
        self.assertFalse(w.complete_weeks([proof],frozen,[decision()],grade_completed_at=NOW.isoformat())[0])

    def test_quota_scoped_public_path_is_idempotent_and_keeps_streams_separate(self):
        q,b,r=fixture();frozen=[dict(season=2026,week=6,website_game_id="999",kickoff_utc=KICK,home="A",away="B")]
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);policy=ROOT/"config/operational-source-policy-v2.json"
            with patch.object(live,"fetch",side_effect=fetcher({"gp":1,"rec":0})),patch.object(live,"now_utc",return_value=NOW),\
                patch("nfl_lab.grading_sources.load_permitted_grading_context",side_effect=ValueError("fictional no supplement")):
                a=w.grade_weekly(root/"state",root/"cache",[q],b,r,stream(),frozen,[decision()],source_policy=policy,clock=lambda:NOW)
                c=w.grade_weekly(root/"state",root/"cache",[q],b,r,stream(),frozen,[decision()],source_policy=policy,clock=lambda:NOW+timedelta(hours=1))
                daily={**stream("primary-daily"),"stream_kind":"primary_daily","horizon_version":"primary-day-v1"}
                other=w.grade_weekly(root/"state",root/"cache",[q],b,r,daily,frozen,[decision()],source_policy=policy,clock=lambda:NOW+timedelta(hours=2))
            self.assertEqual(a["new_revisions"],11);self.assertEqual(c["new_revisions"],0)
            self.assertEqual(a["outcomes"],c["outcomes"]);self.assertEqual(a["weeks"],c["weeks"])
            self.assertNotEqual(a["outcomes"][0]["stream_id"],other["outcomes"][0]["stream_id"])
            self.assertFalse(list((w.stream_root(root/"state",stream())/"collector/forecasts").glob("*")))
            receipts=list(state.records(w.stream_root(root/"state",stream()),"weekly_grading_receipts"))
            self.assertTrue(all("outcomes" not in x for x in receipts))

    def test_unsealed_cli_hook_has_no_resource_or_source_side_effect(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"prep.json";p.write_text(json.dumps(dict(schema_version=w.VERSION+"-plan",state="PREPARED",execution_authorized=False,review={})))
            import resource
            with patch.object(resource,"setrlimit",side_effect=AssertionError("resource mutation before GO")),patch.object(live,"fetch",side_effect=AssertionError("source call")):
                with self.assertRaisesRegex(ValueError,"not execution authority"):w.grade_from_plan(p,w.binding(p)["sha256"],Path(d)/"state",Path(d)/"cache",source_policy=None)


if __name__=="__main__":unittest.main()
