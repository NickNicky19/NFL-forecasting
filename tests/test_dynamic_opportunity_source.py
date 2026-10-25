"""Twelve new fictional contracts; no NFL source/model/storage/network calls."""
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import unittest

from nfl_lab import dynamic_opportunity_source as source
from nfl_lab import dynamic_opportunity_study as study
from nfl_lab import dynamic_opportunity_core as core


def fixture():
    first = datetime(2020, 8, 1, 17, tzinfo=timezone.utc)
    calendar = []; roster = []; raw = []; history = []
    for index in range(4):
        kickoff = first + timedelta(days=9*index)
        for own, other in (("FICTIONAL_A", "FICTIONAL_B"), ("FICTIONAL_B", "FICTIONAL_A")):
            calendar.append(dict(game_id=f"fictional-{index}", season=2020, week=index+1, season_type="REG",
                team=own, opponent=other, kickoff_utc=kickoff.isoformat(), available_utc=(kickoff+timedelta(days=7)).isoformat()))
        roster.append(dict(gsis_id="fictional-player", season=2020, week=index+1, game_type="REG", team="FICTIONAL_A",
                           position="RB", status="INA", source_row_id=f"r:{index}", source_body_sha256="2"*64))
        raw.append(dict(player_id="fictional-player", season=2020, week=index+1, season_type="REG", team="FICTIONAL_A",
                        carries=0, targets=2, receptions=1, receiving_yards=-2,
                        source_row_id=f"s:{index}", source_body_sha256="1"*64))
        history.append(dict(player_id="fictional-player", season=2020, week=index+1, game_id=f"fictional-{index}",
            team="FICTIONAL_A", opponent="FICTIONAL_B", position="RB", kickoff_utc=kickoff.isoformat(),
            outcome_available_utc=(kickoff+timedelta(days=7)).isoformat(), participation_state="played",
            participation_evidence="fictional_positive_action", source_policy="fictional-bound-policy", stats_observed=True,
            rush_att=0, rec_tgt=2, rec=1, rec_yd=-2))
    offer = dict(calendar[-2], offer_id="fictional-offer", player_id="fictional-player", position="RB",
                 cutoff_utc=calendar[-2]["kickoff_utc"], outcome_available_utc=calendar[-2]["available_utc"], f_team_rush_att_mean3=10.)
    return calendar, roster, raw, history, offer


class NoPrimitive(dict):
    def get(self, key, *args):
        if key in ("carries", "targets", "receptions", "receiving_yards"):
            raise AssertionError("unavailable source primitive accessed")
        return super().get(key, *args)


class ProducerContracts(unittest.TestCase):
    def test_01_calendar_exact_reg_projection_and_reciprocal_context(self):
        rows = [dict(game_id="fictional-calendar", season="2020", week="1", game_type="REG", gameday="2020-09-10",
                     gametime="13:00", away_team="FICTIONAL_A", home_team="FICTIONAL_B")]
        result = source.calendar_rows(rows)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["kickoff_utc"], "2020-09-10T17:00:00+00:00")
        with self.assertRaises(ValueError):source.calendar_rows([{**rows[0], "actual_score": 7}])

    def test_02_strict_seven_day_and_no_future_primitive_access(self):
        cal, _, raw, _, _ = fixture(); cutoff = cal[0]["available_utc"]
        self.assertEqual(source.allowed_periods(cal, cutoff), [])
        credits, _ = source.credit_rows([NoPrimitive(raw[0])], cal, task="rush_att", cutoff=cutoff,
                                         statistics_sha256_by_season={"2020":"1"*64})
        self.assertEqual(credits, [])

    def test_03_physical_identity_order_and_duplicate_occurrences(self):
        identity = dict(player_id="fictional-player", season=2020, week=1, season_type="REG", team="FICTIONAL_A")
        post = {**identity, "season_type":"POST"}
        result = source.attach_row_pointers([post, identity, identity], [identity, identity], body_sha256="1"*64,
                                            kind="statistics", periods=[(2020,1,"FICTIONAL_A")])
        self.assertNotEqual(result[0]["source_row_id"], result[1]["source_row_id"])
        self.assertEqual(result[0]["source_row_id"],"1"*64+":row:1")
        with self.assertRaises(ValueError):source.attach_row_pointers([identity, identity], [identity], body_sha256="1"*64,
                                            kind="statistics", periods=[(2020,1,"FICTIONAL_A")])

    def test_04_all_position_credits_orphan_and_explicit_zero_survive(self):
        cal, _, raw, _, offer = fixture()
        rows = [raw[0], {**raw[0], "player_id":"fictional-quarterback", "carries":3, "source_row_id":"s:qb"},
                {**raw[0], "player_id":None, "carries":2, "source_row_id":"s:orphan"}]
        credits, unassigned = source.credit_rows(rows, cal, task="rush_att", cutoff=offer["cutoff_utc"],
                                                 statistics_sha256_by_season={"2020":"1"*64})
        self.assertEqual([r["count"] for r in credits], [0,3,2]); self.assertEqual(unassigned, [])
        self.assertIsNone(credits[-1]["player_id"])

    def test_05_week1_anchor_required_and_missing_slot_never_filled(self):
        cal, roster, _, _, offer = fixture()
        spell, members, _ = source.membership_for_offer(offer, cal, roster, membership_manifest_sha256="3"*64)
        self.assertEqual(spell["state"], "qualified"); self.assertTrue(all(m["membership_state"]=="qualified_same_spell" for m in members))
        spell, _, _ = source.membership_for_offer(offer, cal, roster[1:], membership_manifest_sha256="3"*64)
        self.assertEqual(spell["state"], "unqualified")
        _, members, _ = source.membership_for_offer(offer, cal, [roster[0],*roster[2:]], membership_manifest_sha256="3"*64)
        self.assertEqual(members[1]["membership_state"], "ambiguous_or_missing_membership")

    def test_06_roster_conflict_duplicates_and_unavailable_rows_not_continuity(self):
        cal, roster, _, _, offer = fixture()
        conflicting = {**roster[0], "team":"FICTIONAL_B", "source_row_id":"r:other"}
        spell, _, audit = source.membership_for_offer(offer, cal, [*roster,conflicting], membership_manifest_sha256="3"*64)
        self.assertEqual(spell["state"], "unqualified"); self.assertTrue(audit["conflicting_team_membership"])
        spell, _, _ = source.membership_for_offer(offer, cal, [*roster,roster[0]], membership_manifest_sha256="3"*64)
        self.assertEqual(spell["state"], "unqualified")
        early = {**offer,"cutoff_utc":cal[0]["available_utc"]}
        spell, _, _ = source.membership_for_offer(early, cal, roster, membership_manifest_sha256="3"*64)
        self.assertEqual(spell["state"], "unqualified")

    def test_07_raw_zero_requires_unchanged_qualified_playing(self):
        cal, _, raw, history, offer = fixture()
        records = source.qualified_player_rows(raw, history, cal, task="rush_att", cutoff=offer["cutoff_utc"])
        self.assertEqual(records[0]["count"],0); self.assertEqual(records[0]["count_support"],"explicit_value")
        history[0]["participation_state"]="unknown"
        records = source.qualified_player_rows(raw, history, cal, task="rush_att", cutoff=offer["cutoff_utc"])
        self.assertIsNone(records[0]["count"])
        history[0]["participation_state"]="played"; history[0]["rush_att"]=1
        with self.assertRaises(ValueError):source.qualified_player_rows(raw, history, cal, task="rush_att", cutoff=offer["cutoff_utc"])

    def test_08_source_gate_explicit_projection_cache_and_clock_preservation(self):
        with self.assertRaises(ValueError):source.ProjectionSource({"state":"DRAFT"},authenticator=lambda x:None)
        cal, roster, raw, history, offer = fixture(); reads=[]
        refs={k:{str(y):dict(path=f"fictional/{k}/{y}",sha256=("1" if k=="statistics" else "2")*64) for y in source.YEARS} for k in ("statistics","rosters")}
        h=dict(path="fictional/history",sha256="3"*64)
        plan=dict(state="FROZEN_ROOT_REVIEWER_SEALED",seal={"fictional":True},qualified_history=h,**refs)
        plan['owned_inputs']=[*refs['statistics'].values(),*refs['rosters'].values(),h]
        def reader(path,columns,filters):
            reads.append((path,columns,filters))
            rows=history[:3] if path==h['path'] else raw[:3] if '/statistics/' in path else roster[:3]
            return [{k:r[k] for k in columns} for r in rows]
        projected=source.ProjectionSource(plan,authenticator=lambda x:{'fake':len(x)},reader=reader)
        projected.advance(cal,offer['cutoff_utc']); number=len(reads); projected.advance(cal,offer['cutoff_utc'])
        self.assertEqual(len(reads),number); self.assertTrue(all(f==[[]] or 'season_type' in str(f) or 'game_type' in str(f) or p==h['path'] for p,c,f in reads))
        with self.assertRaises(ValueError):projected.advance(cal,cal[0]['kickoff_utc'])
        contexts=source.offer_contexts([offer],cal,query_reference={'sha256':'4'*64},task='rush_att')
        self.assertEqual(contexts[0]['cutoff_utc'],offer['cutoff_utc']); self.assertEqual(contexts[0]['cutoff_utc'],contexts[0]['kickoff_utc'])

    def test_09_exact54_sequence_and_global_label_gate(self):
        self.assertEqual(len(study.slots()),54); self.assertEqual(sum(s['phase']=='development' for s in study.slots()),24)
        sequence=study.Sequence()
        with self.assertRaises(ValueError):sequence.before_final_labels()
        with self.assertRaises(ValueError):sequence.reserve(sequence.planned[0],600001)
        for slot in sequence.planned:
            if slot['phase']=='forward' and not sequence.selection_frozen:sequence.freeze_selection('fictional-selection')
            sequence.reserve(slot,1); sequence.freeze(slot,1,'fictional-binding')
            if slot==[s for s in sequence.planned if s['year']==slot['year']][-1]:sequence.freeze_year(slot['year'],'fictional-year')
        sequence.freeze_global('fictional-global'); sequence.before_final_labels()
        with self.assertRaises(ValueError):sequence.reserve(sequence.planned[-1],1)

    def test_10_fixed_selection_ties_and_equal_common_cohort(self):
        losses={task:{s:dict(squared_error_sum=1.,rows=1,cohort_sha256='fictional-common') for s in core.SETTINGS} for task in study.TASKS}
        self.assertEqual(set(study.select_once(losses).values()),{'smooth-H8-k100'})
        losses['rush_att']['smooth-H2-k25']['cohort_sha256']='different'
        with self.assertRaises(ValueError):study.select_once(losses)

    def test_11_static_fixed_efficiency_and_auxiliary_controls(self):
        train=core.Slot('fictional-player','FICTIONAL_A',2019,'fictional-2019','rush_att','RB','fictional-prior',
            '2019-08-01T17:00:00+00:00','2019-08-08T17:00:00+00:00','played',True,2,10)
        share_prior=core.form_prior([train],task='rush_att',role='RB',query_season=2020,training_before_utc='2020-08-01T00:00:00+00:00')
        query=core.Query('fictional-player','FICTIONAL_A',2020,'fictional-2020','rush_att','RB','fictional-query',
            '2020-09-01T17:00:00+00:00','2020-09-01T17:00:00+00:00',True,'start_of_season_or_spell')
        slot=core.Slot('fictional-player','FICTIONAL_A',2020,'fictional-2020','rush_att','RB','fictional-history',
            '2020-08-01T17:00:00+00:00','2020-08-08T17:00:00+00:00','played',True,3,10)
        request=dict(state='READY_CORE_REQUEST',core_query=query.manifest(),history=[slot.manifest()],volume=10.,volume_supported=True)
        point=study.predict_request(request,share_prior,setting='smooth-H2-k25',static=True)
        self.assertAlmostEqual(point['point'],10*(25*.2+3)/(25+10))
        prior=dict(state='READY',catch_rate=.5,YPT=2.)
        efficiency=study.fixed_efficiency(prior,[dict(source_qualified=True,participation_state='played',targets=0,receptions=0,receiving_yards=-2)])
        self.assertLess(efficiency['YPT'],2.); self.assertEqual(study.propagated_point(2,efficiency,'rec'),1.)
        self.assertEqual(study.auxiliary_simple([None,0,2],1.,window=3),1.)
        self.assertIsNone(study.propagated_point(None,efficiency,'rec_yd'))
        with self.assertRaises(ValueError):study.fixed_efficiency(prior,[dict(source_qualified=True,participation_state='played',targets=0,receptions=1,receiving_yards=0)])

    def test_12_orchestration_mock_phase_boundaries_and_preflight_rejection(self):
        estimate=study.retention_estimate([1]*54,loss_rows=100,request_rows=4,
            scored_label_view=dict(contract='FACTORED_SCORED_LABEL_VIEW',context_and_forecast_bindings_required=True,unique_label_rows=5),
            paired_loss_view=dict(contract='REPLAYABLE_PAIRED_LOSS_VIEW',original_scorer_and_all_scored_bindings_required=True,views=2))
        self.assertEqual((estimate['logical_scored_rows'],estimate['logical_paired_loss_rows']),(54,100))
        class Backend:
            state='FROZEN_ROOT_REVIEWER_SEALED';version=study.VERSION
            def __init__(self):self.events=[]
            def verify_owned_entry(self):self.events.append('entry')
            def verify_owned_exit(self):self.events.append('exit')
            def consume_once(self):self.events.append('consume')
            def preflight(self,slots):return dict(within_row_cap=True,within_retention_estimate=True)
            def save_plan_and_estimate(self,x):pass
            def guard(self):pass
            @contextmanager
            def cumulative_phase_limit(self,name,wall,cpu):self.events.append(('phase',name,wall,cpu));yield
            @contextmanager
            def package_limit(self,wall,cpu):yield
            def prepare_year(self,year,prior_kinds):self.events.append(('prepare',year))
            def query_count(self,year):return 1
            def forecast_package(self,slot,selected,compute):self.events.append(('forecast',slot['year']));return 'fictional-body'
            def freeze_year(self,y):self.events.append(('year',y));return 'fictional-year'
            def development_loss_sums(self):return {t:{s:dict(squared_error_sum=1.,rows=1,cohort_sha256='fictional') for s in core.SETTINGS} for t in study.TASKS}
            def freeze_selection(self,s):self.events.append('selection');return 'fictional-selection'
            def freeze_global(self,slots,s):self.events.append('global');return 'fictional-global'
            def score_saved_rows_only(self):self.events.append('score')
            def report_same_evaluator(self,replicates,seed,all_targets):return (replicates,seed,len(all_targets))
            def retain_failure(self,error,sequence):self.events.append('failed')
        backend=Backend();self.assertEqual(study.run_study(backend),(500,1703,12))
        self.assertLess(backend.events.index('global'),backend.events.index('score'));self.assertEqual(backend.events[-1],'exit')
        backend=Backend();backend.preflight=lambda slots:dict(within_row_cap=True,within_retention_estimate=False)
        with self.assertRaises(RuntimeError):study.run_study(backend)
        self.assertNotIn('score',backend.events);self.assertEqual(backend.events[-2:],['failed','exit'])


if __name__ == '__main__':unittest.main()
