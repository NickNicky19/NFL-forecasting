"""Four NEW fictional consumer contracts, with no original-suite imports."""
from copy import deepcopy
from io import BytesIO
from pathlib import Path
import unittest
from unittest.mock import patch

from offline_report_imports_v1 import offline_dependency_imports
with offline_dependency_imports():
    import numpy as np
    import pandas as pd
    from nfl_lab import conformal_intervals as core
    from nfl_lab import conformal_interval_campaign as campaign
    from nfl_lab.source_matched_reporting import _bootstrap  # resolve offline imports before effects guard


def frame(year=2023, target='rush_att', count=8):
    clocks = pd.to_datetime([f'{year}-09-01T17:00:00Z']*count, utc=True)
    return pd.DataFrame(dict(season=np.full(count, year, dtype=np.int32), week=np.arange(1,count+1,dtype=np.int32),
        game_id=[f'fictional-{year}-{i}' for i in range(count)], player_id=['fictional-player']*count,
        team=['FICTIONAL_A']*count, opponent=['FICTIONAL_B']*count, position=['RB']*count,
        kickoff_utc=clocks, cutoff_utc=clocks, target=target, method='leaf_cdf', primary_role=True,
        fallback='', history_state='fictional_cold', p10=0., p90=2., actual=0.,
        participation_state='played', outcome_state='played_zero'))


def query(year):
    result = frame(year)[list(campaign.CONTEXT)].copy()
    result['outcome_available_utc'] = result.kickoff_utc + pd.Timedelta(days=7)
    return result


class CaptureSession(campaign.Session):
    def __init__(self):
        self.gate = campaign.LabelGate(); self.radii = {}; self.bindings = {}; self.frames = {}; self.documents = {}
        self.spec = dict(cdf={str(y):{t:dict(path=f'fictional/{y}/{t}',sha256='1'*64) for t in core.SUPPORTS}
            for y in (2022,2023,2024)}, queries={str(y):dict(path=f'fictional/query/{y}',sha256='2'*64) for y in (2022,2023,2024)})
        self.intervals = {}; self.labels = {}; self.predictions = {}; self.guard=lambda:None

    def prediction(self, year, target):
        result = frame(year, target).drop(columns=['actual','participation_state','outcome_state'])
        if target == 'rush_yd':
            result['p10'], result['p90'] = -3., -1.
        result.loc[1,'p10'] = np.nan
        result.loc[0,'fallback'] = 'fictional_original_fallback'
        return result

    def write(self, relative, value):
        self.documents[relative] = deepcopy(value); self.bindings[relative]='3'*64

    def frame(self, relative, value):
        self.frames[relative] = value.copy(); self.bindings[relative]='4'*64


class IntervalConsumerContracts(unittest.TestCase):
    def test_01_exact_nine_contexts_reject_reordered_dtype_clock_and_period_repairs(self):
        saved, original = frame(), query(2023)
        self.assertTrue(campaign.exact_clock_context(original,saved,year=2023,target='rush_att')['ordered_identity_clock_match'])
        for changed in (saved.iloc[::-1].reset_index(drop=True), saved.assign(week=saved.week.astype('int64')),
                saved.assign(cutoff_utc=saved.cutoff_utc+pd.Timedelta(nanoseconds=1))):
            with self.assertRaises(AssertionError):
                campaign.exact_clock_context(original,changed,year=2023,target='rush_att')
        with self.assertRaisesRegex(ValueError,'one-sided'):
            campaign.exact_clock_context(original,saved.assign(season_type='REG'),year=2023,target='rush_att')

    def test_02_mock33_cached_projections_and_labels_remain_frozen_until_all_ten(self):
        owner=campaign.Session.__new__(campaign.Session)
        owner.spec=dict(categories={t:dict(primary_roles=['RB']) for t in core.SUPPORTS},cdf={})
        owner.queries={y:query(y) for y in (2022,2023,2024)}
        owner.predictions={};owner.labels={};owner.entry_refs={};owner.owned={};owner.projections=[];owner.rows_read=0
        owner.gate=campaign.LabelGate();owner.guard=lambda:None;owner.write=lambda *a:None
        files={};calls=[]
        for year in (2022,2023,2024):
            owner.spec['cdf'][str(year)]={}
            path=f'fictional/query/{year}';files[path]=query(year)
            owner.entry_refs[path]=True;owner.owned[path]='1'*64
            for target in core.SUPPORTS:
                path=f'fictional/{year}/{target}';files[path]=frame(year,target)
                owner.entry_refs[path]=True;owner.owned[path]='1'*64
                owner.spec['cdf'][str(year)][target]=dict(path=path,sha256='1'*64,rows=8,columns=list(files[path]),year=year)
        def projected(path,columns):
            calls.append((path,tuple(columns)))
            return files[path][columns].copy()
        with patch.object(pd,'read_parquet',side_effect=projected):
            for year in (2022,2023,2024):
                path=f'fictional/query/{year}'
                owner.read(dict(path=path,sha256='1'*64,rows=8),list(query(year)),lane='query_clock')
                for target in core.SUPPORTS:
                    owner.prediction(year,target);owner.prediction(year,target)
            self.assertEqual(len(calls),33)
            self.assertTrue(all('actual' not in columns for _,columns in calls))
            with self.assertRaisesRegex(ValueError,'before complete year'):
                owner.label(2023,'rush_att')
            self.assertEqual(len(calls),33)
            with self.assertRaises(ValueError):owner.gate.freeze_year(2023,list(core.SUPPORTS)[:-1])
            owner.gate.freeze_year(2023,list(core.SUPPORTS))
            a=owner.label(2023,'rush_att');b=owner.label(2023,'rush_att')
            self.assertIs(a,b);self.assertEqual(len(calls),34)
            self.assertEqual(a.actual.tolist(),[0.]*8)

    def test_03_all20_radius_consumers_preserve_ordinals_missing_fallback_and_codec(self):
        owner=CaptureSession()
        original={}
        for year in (2023,2024):
            for target in core.SUPPORTS:
                radius=dict(version=core.VERSION,target=target,alpha=.2,radius=1.,state='RADIUS_FROZEN',
                    evaluation_season=year,evaluation_start_utc=f'{year}-09-01T17:00:00+00:00')
                owner.radii[year,target]=radius;original[year,target]=deepcopy(radius)
            owner.freeze_year(year)
        self.assertEqual(owner.radii,original);self.assertEqual(len(owner.frames),20)
        self.assertEqual(owner.gate.frozen_years,{2023,2024})
        for name,data in owner.frames.items():
            self.assertEqual(data.ordinal.tolist(),list(range(8)))
            self.assertEqual(data.status.iloc[1],campaign.INTERVAL_CODES['ABSTAIN_MISSING_BASE_INTERVAL'])
            self.assertTrue(pd.isna(data.interval_lower.iloc[1]))
            body=BytesIO();data.to_parquet(body,index=False,compression='zstd');body.seek(0)
            pd.testing.assert_frame_equal(data,pd.read_parquet(body),check_dtype=True,check_exact=True)
        signed=owner.frames['private/intervals/2023/rush_yd.parquet']
        self.assertEqual((signed.interval_lower.iloc[0],signed.interval_upper.iloc[0]),(-4.,0.))
        self.assertEqual(owner.prediction(2023,'rush_att').fallback.iloc[0],'fictional_original_fallback')

    def test_04_interval_evaluator_and_team_opponent_aggregates_reuse_same_rows(self):
        data=frame()
        data['interval_lower'],data['interval_upper'],data['interval_status']=0.,3.,'RADIUS_FROZEN'
        report=core.evaluate_interval_frame(data,target='rush_att',guard=lambda:None)
        self.assertEqual(report['reports'][0]['paired_rows'],8)
        self.assertEqual(report['reports'][0]['metrics']['interval_score']['mean_delta'],1.)
        self.assertEqual(report['reports'][0]['metrics']['covered']['mean_delta'],0.)
        self.assertEqual(report['reports'][0]['metrics']['interval_score']['week']['interval'],[1.,1.])
        groups=campaign.subgroup_table(data,'rush_att')
        for dimension in ('team','opponent','player_id','position'):
            group=groups.loc[(groups.dimension==dimension)&(groups.population=='all_offered')].iloc[0]
            self.assertEqual((group.planned_rows,group.paired_rows,group.supported_zero),(8,8,8))
        changed=data.copy();changed.loc[0,['actual','participation_state','outcome_state']]=[np.nan,'unknown','unknown']
        result=core.evaluate_interval_frame(changed,target='rush_att',guard=lambda:None)
        self.assertEqual(result['reports'][0]['paired_rows'],7)
        self.assertEqual(result['reports'][0]['metrics']['interval_score']['game']['reason'],'fewer_than_8_clusters')


if __name__=='__main__':
    unittest.main()
