"""Six NEW fictional consumer methods; no original suites or real source I/O."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import unittest

from tools.offline_report_imports_v1 import offline_dependency_imports

# The unchanged context suppresses only urllib3's import-time IPv6 probe.
# Socket/process audit denials remain active and the capability is restored.
with offline_dependency_imports():
    import numpy as np
    import pandas as pd
    from nfl_lab import dynamic_opportunity_backend as backend

from nfl_lab import dynamic_opportunity_source_helpers as helpers
from nfl_lab import dynamic_opportunity_source as source
from nfl_lab import dynamic_opportunity_core as core
from nfl_lab.state import digest, utc


def fixture():
    calendar=[]; raw=[]; rosters=[]; histories=[]; queries=[]
    statistics={str(y):{'sha256':str(y%10)*64} for y in source.YEARS}
    for year,weeks in ((2019,1),(2020,4)):
        first=datetime(year,1,1,17,tzinfo=timezone.utc)
        for index in range(weeks):
            stamp=first+timedelta(days=10*index);gid=f'fictional-game-{year}-{index+1}'
            for team,opponent in (('FICTIONAL_A','FICTIONAL_B'),('FICTIONAL_B','FICTIONAL_A')):
                calendar.append(dict(game_id=gid,season=year,week=index+1,season_type='REG',team=team,opponent=opponent,
                    kickoff_utc=stamp.isoformat(),available_utc=(stamp+timedelta(days=7)).isoformat()))
            unknown=year==2020 and index==1
            carry=0 if year==2020 else 2
            target=0 if unknown else 4
            reception=0 if unknown else 2
            yards=0 if unknown else -4
            for ordinal,(pid,c,t,catches,production) in enumerate((
                ('fictional-player',carry,target,reception,yards),
                ('fictional-quarterback',8,0,0,0),
                ('fictional-other-receiver',0,6,3,12))):
                raw.append(dict(player_id=pid,season=year,week=index+1,season_type='REG',team='FICTIONAL_A',
                    carries=c,targets=t,receptions=catches,receiving_yards=production,
                    source_row_id=f'fictional-raw-{year}-{index}-{ordinal}',source_body_sha256=statistics[str(year)]['sha256']))
            rosters.append(dict(gsis_id='fictional-player',season=year,week=index+1,game_type='REG',team='FICTIONAL_A',
                position='RB',status='INA',source_row_id=f'fictional-roster-{year}-{index}',source_body_sha256='a'*64))
            histories.append(dict(player_id='fictional-player',season=year,week=index+1,game_id=gid,team='FICTIONAL_A',
                opponent='FICTIONAL_B',position='RB',kickoff_utc=stamp.isoformat(),outcome_available_utc=(stamp+timedelta(days=7)).isoformat(),
                participation_state='unknown' if unknown else 'played',participation_evidence='fictional-qualified-source',
                source_policy='fictional-pinned-qualifier',stats_observed=True,rush_att=None if unknown else carry,
                rec_tgt=None if unknown else target,rec=None if unknown else reception,rec_yd=None if unknown else yards))
            if year==2020:
                queries.append(dict(season=year,week=index+1,game_id=gid,player_id='fictional-player',team='FICTIONAL_A',
                    opponent='FICTIONAL_B',position='RB',kickoff_utc=stamp.isoformat(),cutoff_utc=stamp.isoformat(),
                    outcome_available_utc=(stamp+timedelta(days=7)).isoformat(),f_team_rush_att_mean3=10.))
    plan=dict(source_policy={'sha256':'1'*64},source_manifest={'sha256':'2'*64},calendar={'sha256':'3'*64},
        qualified_history={'sha256':'4'*64},qualification_policy={'sha256':'5'*64},statistics=statistics,
        rosters={str(y):{'sha256':'a'*64} for y in source.YEARS})
    policy=dict(schema_version='dynamic-opportunity-history-replay-v2-20261023-policy',execution_lane='EXPOSED_HISTORICAL_REPLAY',
        source_policy_sha256='1'*64,query_cutoff_rule='cutoff_utc_at_or_before_kickoff_utc',
        source_availability_rule='kickoff_plus_7_days_strictly_before_cutoff_utc',
        original_clocks='PRESERVE_NO_EDITS_OR_EPSILON',prospective_issuance='FORBIDDEN')
    class FakeProjection:
        def __init__(self):
            self.cache={k:[] for k in ('statistics','rosters','qualified_history')};self.calls=[];self.seen=set()
        def advance(self, supplied_calendar, cutoff):
            moment=utc(cutoff)
            if self.calls and moment<self.calls[-1]:raise AssertionError('fake source rewind')
            self.calls.append(moment)
            periods={(g['season'],g['week'],g['team']):g for g in supplied_calendar}
            for kind,rows in (('statistics',raw),('rosters',rosters),('qualified_history',histories)):
                for index,row in enumerate(rows):
                    game=periods[(row['season'],row['week'],row['team'])]
                    if utc(game['available_utc'])<moment and (kind,index) not in self.seen:
                        self.cache[kind].append(row);self.seen.add((kind,index))
            return self.cache
    projection=FakeProjection();annual=helpers.AnnualInputs(projection,calendar,plan,policy)
    return annual,projection,queries,calendar


def prepared():
    annual,projection,queries,calendar=fixture()
    annual.prepare(2020,queries,{'path':'fictional-annual-context','sha256':'b'*64,'bytes':111},('rush_att','rec_tgt'))
    return annual,projection,queries,calendar


class NoPrimitive(dict):
    def get(self,key,*args):
        if key in ('targets','receptions','receiving_yards','rec_tgt','rec','rec_yd','carries','rush_att'):
            raise AssertionError('future cached primitive accessed')
        return super().get(key,*args)


class BackendConsumerContracts(unittest.TestCase):
    def test_01_persisted_jsoncell_codec_roundtrip_shared_null_zero_signed(self):
        annual,_,_,_=prepared()
        original=annual.requests_for_year(2020,'rush_att')
        original[2]['fictional_signed_probe']=-3.5
        packet=annual.factored_requests(2020,'rush_att')
        manifest={k:v for k,v in packet.items() if k not in ('records','tables')}
        manifest.update(records_binding={'path':'fictional-records','sha256':'c'*64},
            table_bindings={name:{'rows':len(rows),'path':'fictional-'+name,'sha256':'d'*64} for name,rows in packet['tables'].items()},
            serializer='payload_json',consumer='nfl_lab.dynamic_opportunity_backend.restore_request_view')
        tables={name:pd.DataFrame({'payload_json':[core.encode_json(row) for row in rows]}) for name,rows in packet['tables'].items()}
        records=pd.DataFrame(packet['records'])
        # Arrow consumers may restore list columns as arrays. Exercise that
        # persisted shape without writing a Parquet or opening any source.
        for key in ('history_indices','slot_audit_indices'):records[key]=records[key].map(np.asarray)
        restored=backend.restore_request_view(manifest,records,tables)
        self.assertEqual(restored,original)
        self.assertEqual(restored[2]['fictional_signed_probe'],-3.5)
        values=[s['player_count'] for r in restored for s in r['history']]
        self.assertIn(0,values);self.assertIn(None,values)
        self.assertLess(len(packet['tables']['proxies']),sum(len(r['slot_audit']) for r in original))
        with self.assertRaises(ValueError):backend.restore_request_view({**manifest,'original_rows':5},records,tables)

    def test_02_cached_future_efficiency_never_enters_earlier_request(self):
        annual,_,_,_=prepared();request=deepcopy(annual.requests_for_year(2020,'rec_tgt')[1])
        annual.prior_vectors[2020]['efficiency_priors']={'RB':dict(state='READY',catch_rate=.5,YPT=2.)}
        future=NoPrimitive(dict(player_id='fictional-player',season=2020,week=18,game_id='fictional-future',team='FICTIONAL_A',
            position='RB',participation_state='played',outcome_available_utc='2020-12-31T00:00:00+00:00'))
        annual.history_by_player['fictional-player'].append(future)
        request['history']=[dict(player_id='fictional-player',team='FICTIONAL_A',game_id='fictional-future')]
        efficiency=annual.efficiency_for_request(2020,request)
        self.assertEqual((efficiency['catch_rate'],efficiency['YPT']),(.5,2.))
        self.assertEqual(efficiency['slots'],['unknown_or_unqualified_no_update'])
        self.assertEqual(annual.efficiency_for_request(2020,request),efficiency)

    def test_03_earlier_role_prior_excludes_current_season_cached_values(self):
        annual,_,queries,_=fixture();cutoff=queries[0]['cutoff_utc'];annual._advance(cutoff)
        annual.raw_by_year[2020].append(NoPrimitive(dict(season=2020)))
        annual.history_by_year[2020].append(NoPrimitive(dict(season=2020)))
        priors,means,audit=annual._prior(2020,'rush_att',cutoff)
        self.assertAlmostEqual(priors['RB'].share,.2)
        self.assertEqual((priors['RB'].total_player_count,priors['RB'].total_repeated_team_exposure),(2,10))
        self.assertEqual(means['RB'],2.)
        self.assertEqual(audit['training_seasons'],[2019]);self.assertFalse(audit['all_nfl_credits_complete'])

    def test_04_both_tasks_prepare_monotonically_preserving_original_ordinals(self):
        annual,projection,queries,_=prepared()
        self.assertEqual(projection.calls,sorted(projection.calls));before=len(projection.calls)
        for task in ('rush_att','rec_tgt'):
            requests=annual.requests_for_year(2020,task)
            self.assertEqual(len(requests),len(queries))
            self.assertEqual([r['offer']['original_query_reference']['row_ordinal'] for r in requests],list(range(4)))
            self.assertEqual(len({r['offer_id'] for r in requests}),4)
            self.assertEqual(requests[0]['state'],'BASELINE_FALLBACK_REQUIRED')
        self.assertEqual(len(projection.calls),before)
        self.assertEqual(annual.prior_vectors[2020]['simple_role_means']['rush_att']['RB'],2.)
        self.assertEqual(annual.prior_vectors[2020]['simple_role_means']['rec_tgt']['RB'],4.)
        with self.assertRaises(ValueError):annual.prepare(2020,queries,{'sha256':'b'*64},('rush_att','rec_tgt'))

    def test_05_exact_nine_context_and_saved_cdf_product_semantics(self):
        query=pd.DataFrame(dict(season=[2022,2022],week=[1,1],game_id=['fictional-context']*2,
            player_id=['fictional-a','fictional-b'],position=['RB','RB'],team=['FICTIONAL_A']*2,opponent=['FICTIONAL_B']*2,
            kickoff_utc=pd.to_datetime(['2022-01-01T17:00:00Z']*2),cutoff_utc=pd.to_datetime(['2022-01-01T17:00:00Z']*2)))
        donor=query.assign(target='rush_att',method='leaf_cdf',mean=[4.75,3.25],median=[0.,-2.],point=[0.,-2.])
        receipt=backend.exact_context(query,donor,target='rush_att',year=2022,method='leaf_cdf')
        self.assertEqual(len(receipt['context']),9);self.assertEqual(receipt['season_type'],'ABSENT_BOTH_FROZEN_LEGACY_PROJECTIONS')
        self.assertEqual(backend.cdf_baseline_point(donor,'count').tolist(),[4.75,3.25])
        self.assertEqual(backend.cdf_baseline_point(donor,'signed_integer').tolist(),[0.,-2.])
        with self.assertRaises(ValueError):backend.exact_context(query,donor.assign(season_type='REG'),target='rush_att',year=2022,method='leaf_cdf')
        with self.assertRaises((ValueError,AssertionError)):backend.exact_context(query,donor.iloc[::-1].reset_index(drop=True),target='rush_att',year=2022,method='leaf_cdf')
        with self.assertRaises((ValueError,AssertionError)):backend.exact_context(query,donor.astype({'season':'float64'}),target='rush_att',year=2022,method='leaf_cdf')

    def test_06_nomination_requires_cdf_and_static_without_release_claim(self):
        def pair(comparator,period):
            return dict(candidate='selected_dynamic',comparator=comparator,population='primary_roles',period=period,
                improvement_pct=3.,candidate_loss=9.7,control_loss=10.,forecast_finite_masks_equal=True,
                candidate_point_metrics=dict(bias_prediction_minus_actual=.5,absolute_error_p95=4.),
                control_literal_point_metrics=dict(bias_prediction_minus_actual=.5,absolute_error_p95=5.))
        periods=('pooled_2022_2024',2022,2023,2024)
        report=dict(pairs=[pair('leaf_cdf',p) for p in periods],matched_static_pairs=[pair('matched_static',p) for p in periods])
        result=backend.development_nomination(report)
        self.assertEqual(result['decision'],'DEVELOPMENT_LEAD_REQUIRES_LATER_CONFIRMATION')
        self.assertFalse(result['release_ready']);self.assertFalse(result['scientific_qualification'])
        missing=deepcopy(report);missing['matched_static_pairs'].pop()
        self.assertEqual(backend.development_nomination(missing)['decision'],'NOT_NOMINATED')
        coverage=deepcopy(report);coverage['pairs'][0]['forecast_finite_masks_equal']=False
        self.assertIn('leaf_cdf:forecast_coverage_changed',backend.development_nomination(coverage)['reasons'])
        adverse=deepcopy(report);adverse['pairs'][-1]['candidate_loss']=10.6
        self.assertIn('leaf_cdf:annual_regression:2024',backend.development_nomination(adverse)['reasons'])


if __name__=='__main__':unittest.main()
