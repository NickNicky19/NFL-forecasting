"""Fictional arithmetic only: no NFL records, sources, fitted models or network."""
from dataclasses import replace
from datetime import datetime,timedelta,timezone
import math
import unittest

from nfl_lab import dynamic_opportunity_core as core


def slot(index=0,*,season=2024,player='fiction-P',role='RB',task='rush_att',c=4,t=20,**changes):
    start=datetime(season,8,1,tzinfo=timezone.utc)+timedelta(days=index*7)
    value=core.Slot(player,'FIC',season,f'FIC-{season}-spell',task,role,f'fiction-{season}-{index}',
        start.isoformat(),(start+timedelta(days=1)).isoformat(),'played',True,c,t)
    return replace(value,**changes)


def query(**changes):
    value=core.Query('fiction-P','FIC',2024,'FIC-2024-spell','rush_att','RB','fiction-target',
        '2024-11-10T18:00:00Z','2024-11-10T17:00:00Z',True,'start_of_season_or_spell')
    return replace(value,**changes)


def prior(**changes):
    records=[slot(0,season=2022,c=2,t=10),slot(1,season=2022,c=3,t=10)]
    value=core.form_prior(records,task='rush_att',role='RB',query_season=2024,training_before_utc='2024-01-01T00:00:00Z')
    return replace(value,**changes)


def forecast(history=(),**changes):
    options=dict(setting='smooth-H2-k100',volume=30.,volume_supported=True);options.update(changes)
    return core.forecast(query(),prior(),history,**options)


def independent_predictive(c,t,a,b):
    value=float(math.comb(t,c))
    for i in range(c):value*=a+i
    for i in range(t-c):value*=b+i
    for i in range(t):value/=a+b+i
    return value


def exhaustive_reference(history,q,p=.25,k=100,h=8):
    a0,b0=k*p,k*(1-p);decay=2**(-1/h);branches=[(1.,a0,b0)]
    # Enumerate even the equivalent first-slot reset/continue paths; no merging.
    for row in (*history,None):
        following=[]
        for weight,a,b in branches:
            for chance,aa,bb in ((1-q,a0+decay*(a-a0),b0+decay*(b-b0)),(q,a0,b0)):
                if row is not None and row.participation_state=='played' and row.player_count is not None:
                    c,t=row.player_count,row.team_count;chance*=independent_predictive(c,t,aa,bb);aa+=c;bb+=t-c
                following.append((weight*chance,aa,bb))
        branches=following
    total=math.fsum(w for w,_,_ in branches)
    return math.fsum(w*a/(a+b) for w,a,b in branches)/total


class DynamicCoreChecks(unittest.TestCase):
    def test_exact_six_settings_and_units(self):
        self.assertEqual(len(core.SETTINGS),6)
        self.assertEqual(core.SETTINGS['smooth-H2-k25'],('smooth',2,25,0.))
        self.assertEqual(core.SETTINGS['changepoint-H8-k100-q1of4'],('changepoint',8,100,.25))

    def test_training_prior_same_individual_exposures(self):
        shared_game=slot(0,season=2022,c=2,t=10)
        other=replace(shared_game,player_id='fiction-other',player_count=3)
        value=core.form_prior([shared_game,other],task='rush_att',role='RB',query_season=2024,training_before_utc='2024-01-01T00:00:00Z')
        self.assertEqual(value.total_repeated_team_exposure,20)
        self.assertEqual(value.unique_supported_team_games,1);self.assertEqual(value.share,.25)

    def test_training_prior_retains_played_zero_but_not_unknown(self):
        records=[slot(0,season=2022,c=2,t=10),slot(1,season=2022,c=0,t=10),
            slot(2,season=2022,c=None,t=None,participation_state='unknown')]
        value=core.form_prior(records,task='rush_att',role='RB',query_season=2024,training_before_utc='2024-01-01T00:00:00Z')
        self.assertEqual(value.share,.1);self.assertEqual(value.training_rows,3);self.assertEqual(value.supported_rows,2)

    def test_training_prior_rejects_future_and_duplicate(self):
        kwargs=dict(task='rush_att',role='RB',query_season=2024,training_before_utc='2024-01-01T00:00:00Z')
        with self.assertRaises(ValueError):core.form_prior([slot(0)],**kwargs)
        row=slot(0,season=2022)
        with self.assertRaises(ValueError):core.form_prior([row,row],**kwargs)

    def test_training_prior_rejects_post_cutoff_availability(self):
        row=slot(0,season=2022,available_utc='2024-01-01T00:00:00Z')
        with self.assertRaises(ValueError):core.form_prior([row],task='rush_att',role='RB',query_season=2024,training_before_utc='2024-01-01T00:00:00Z')

    def test_boundary_and_absent_prior_require_fallback(self):
        kwargs=dict(task='rush_att',role='RB',query_season=2024,training_before_utc='2024-01-01T00:00:00Z')
        for records in ([],[slot(0,season=2022,c=0,t=20)],[slot(0,season=2022,c=20,t=20)]):
            p=core.form_prior(records,**kwargs)
            result=core.forecast(query(),p,(),setting='smooth-H2-k100',volume=30,volume_supported=True)
            self.assertEqual(result['state'],'BASELINE_FALLBACK_REQUIRED');self.assertIsNone(result['point'])

    def test_paired_support_never_clips_or_imputes(self):
        for c,t in ((-1,20),(.5,20),(21,20),(True,20),(1,float('nan'))):
            ok,reason,_,_=core.paired_count(slot(c=c,t=t))
            self.assertFalse(ok);self.assertIn(reason,('invalid_count_support','player_exceeds_team_count'))
        self.assertEqual(core.paired_count(slot(c=None))[1],'missing_player_count_no_observation')

    def test_unknown_and_DNP_do_not_become_played_zero(self):
        unknown=slot(c=0,participation_state='unknown')
        dnp=slot(c=0,participation_state='DNP')
        for row in (unknown,dnp):self.assertFalse(core.paired_count(row)[0])
        self.assertTrue(core.paired_count(slot(c=0))[0])
        self.assertEqual(core.paired_count(replace(dnp,source_qualified=False))[1],'unqualified_DNP_no_observation')

    def test_supported_zero_exposure_is_valid(self):
        self.assertEqual(core.paired_count(slot(c=0,t=0)),(True,'supported_zero_exposure',0,0))
        self.assertEqual(core.beta_binomial_logmass(0,0,25.,75.),0.)

    def test_cold_start_retains_training_prior(self):
        for setting in core.SETTINGS:
            result=forecast(setting=setting)
            self.assertEqual(result['state'],'READY_POINT');self.assertEqual(result['share'],.25)
            self.assertEqual(result['point'],7.5);self.assertEqual(len(result['components']),1)

    def test_smooth_one_step_ahead_matches_exact_decay(self):
        result=forecast([slot(c=6,t=20)])
        decay=2**(-.5);expected=(25+decay*6)/(100+decay*20)
        self.assertAlmostEqual(result['share'],expected,places=14)
        self.assertEqual(result['forecast_transition'],'ONE_OBSERVATION_FREE_TEAM_GAME')

    def test_missing_slot_consumes_time_without_zero_update(self):
        observed=slot(c=10,t=20);missing=slot(1,c=None,t=None,participation_state='unknown')
        result=forecast([observed,missing]);decay=2**(-.5)
        self.assertAlmostEqual(result['share'],(25+decay**2*10)/(100+decay**2*20),places=14)
        zero=forecast([observed,slot(1,c=0,t=20)])
        self.assertNotEqual(result['share'],zero['share'])
        self.assertEqual(result['slots'][1]['participation_state'],'unknown')

    def test_beta_binomial_matches_independent_product(self):
        for c,t in ((0,3),(2,4),(5,5)):
            value=math.exp(core.beta_binomial_logmass(c,t,25.,75.))
            self.assertAlmostEqual(value,independent_predictive(c,t,25.,75.),places=12)

    def test_change_point_matches_exhaustive_paths(self):
        rows=[slot(c=1,t=4),slot(1,c=None,t=None,participation_state='unknown'),slot(2,c=4,t=4)]
        for setting,q in [('changepoint-H8-k100-q1of16',1/16),('changepoint-H8-k100-q1of4',1/4)]:
            result=forecast(rows,setting=setting)
            self.assertAlmostEqual(result['share'],exhaustive_reference(rows,q),places=12)
            self.assertEqual(result['numeric_distribution'],'NONE');self.assertFalse(result['joint_allocation'])

    def test_change_point_predictive_reset_present_without_future_label(self):
        result=forecast([slot(c=10,t=20)],setting='changepoint-H8-k100-q1of4')
        decay=2**(-1/8);continued=(25+decay*10)/(100+decay*20)
        self.assertAlmostEqual(result['share'],.25*.25+.75*continued,places=13)
        self.assertEqual(len(result['components']),2)

    def test_eight_history_slots_bound_nine_components(self):
        rows=[slot(i,c=i%5,t=20) for i in range(8)]
        q=query(window_origin='last_eight_team_games')
        for setting in ('changepoint-H8-k100-q1of16','changepoint-H8-k100-q1of4'):
            result=core.forecast(q,prior(),rows,setting=setting,volume=30,volume_supported=True)
            self.assertEqual(result['state'],'READY_POINT');self.assertEqual(len(result['components']),9)
            self.assertAlmostEqual(math.fsum(math.exp(c['logweight']) for c in result['components']),1.,places=13)

    def test_short_window_requires_true_boundary_declaration(self):
        q=query(window_origin='last_eight_team_games')
        result=core.forecast(q,prior(),[slot()],setting='smooth-H2-k100',volume=30,volume_supported=True)
        self.assertEqual(result['state'],'BASELINE_FALLBACK_REQUIRED')
        q=query(selected_slots_complete=False)
        result=core.forecast(q,prior(),[],setting='smooth-H2-k100',volume=30,volume_supported=True)
        self.assertEqual(result['state'],'BASELINE_FALLBACK_REQUIRED')

    def test_cross_team_season_or_spell_requires_reset(self):
        for row in (slot(team='OTHER'),slot(spell_id='different'),slot(season=2023)):
            self.assertEqual(forecast([row])['state'],'BASELINE_FALLBACK_REQUIRED')

    def test_duplicate_unsorted_or_target_history_rejected(self):
        histories=([slot(),slot()],[slot(1),slot(0)],[slot(game_id='fiction-target')])
        for rows in histories:self.assertEqual(forecast(rows)['state'],'BASELINE_FALLBACK_REQUIRED')

    def test_strict_cutoff_and_naive_clock_rejected(self):
        for row in (slot(available_utc=query().cutoff_utc),slot(available_utc='2024-08-02T00:00:00')):
            self.assertEqual(forecast([row])['state'],'BASELINE_FALLBACK_REQUIRED')
        row=slot(c=None,t=None,participation_state='unknown',available_utc=query().cutoff_utc)
        self.assertEqual(forecast([row])['state'],'READY_POINT')

    def test_explicit_zero_volume_differs_from_missing_invalid(self):
        self.assertEqual(forecast(volume=0)['point'],0.)
        for volume in (None,True,-1,float('inf'),float('nan')):
            self.assertEqual(forecast(volume=volume)['state'],'BASELINE_FALLBACK_REQUIRED')
        self.assertEqual(forecast(volume=30,volume_supported=False)['state'],'BASELINE_FALLBACK_REQUIRED')

    def test_JSON_roundtrip_determinism_and_exact_contract(self):
        request=core.request_manifest(query(),prior(),[slot()],setting='smooth-H8-k25',volume=30.25,volume_supported=True)
        original=core.forecast_manifest(request);roundtrip=core.forecast_manifest(core.decode_json(core.encode_json(request)))
        self.assertEqual(core.encode_json(original),core.encode_json(roundtrip))
        bad=dict(request,unexpected='forbidden')
        with self.assertRaises(ValueError):core.forecast_manifest(bad)
        with self.assertRaises(ValueError):core.decode_json('{"value":NaN}')
        with self.assertRaises(ValueError):core.decode_json('{"value":1,"value":2}')

    def test_prior_JSON_corruption_cannot_supply_fake_share(self):
        value=prior().manifest();value['share']=.5
        with self.assertRaises(ValueError):core.Prior.from_manifest(value)
        value=prior().manifest();value['version']='new-version'
        with self.assertRaises(ValueError):core.Prior.from_manifest(value)

    def test_unregistered_setting_does_not_create_forecast(self):
        self.assertEqual(forecast(setting='arbitrary-injury-haircut')['state'],'BASELINE_FALLBACK_REQUIRED')
        result=forecast([slot(c=21,t=20)])
        self.assertIsNone(result['point']);self.assertIn('player_exceeds_team_count',result['reason'])
        self.assertEqual(result['participation_probability'],'UNAVAILABLE')


if __name__=='__main__':unittest.main()
