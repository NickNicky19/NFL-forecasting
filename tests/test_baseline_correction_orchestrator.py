"""New orchestration checks using fictional tables and mocked correction fits."""
from contextlib import ExitStack,nullcontext
import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import baseline_correction_orchestrator as run
from baseline_correction_supervisor import fit_guard


def categories():
    count={'pass_att','pass_cmp','pass_int','pass_td','rush_att','rec'}
    return {target:dict(state='BLOCKED' if target=='fantasy_ppr' else 'READY',
        support='bernoulli' if target=='anytime_td' else 'count' if target in count else 'signed_integer',
        primary_roles=['QB'] if target.startswith('pass_') else ['RB','WR','TE'],modeled_roles=['QB','RB','WR','TE'])
        for target in run.shared.models.TARGETS}


def query(year):
    frame=pd.DataFrame(dict(player_id=['fiction-Q','fiction-R','fiction-W','fiction-T'],season=[year]*4,
        week=[1]*4,game_id=[f'fiction-{year}']*4,position=['QB','RB','WR','TE'],team=['FIC']*4,opponent=['OTH']*4,
        kickoff_utc=[f'{year}-09-08T18:00:00Z']*4,cutoff_utc=[f'{year}-09-08T16:00:00Z']*4,
        feature_max_source_available_utc=[f'{year}-09-01T15:00:00Z']*4,
        f_player_games_prior=[0.,np.nan,2.,3.],f_team_pass_att_mean3=[30.]*4,
        f_team_rush_att_mean3=[20.]*4,f_team_offense_plays_mean3=[60.]*4))
    for stat in ('pass_att','rush_att','rec_tgt'):
        frame[f'f_player_{stat}_mean3']=[0.,np.nan,3.,4.]
        frame[f'f_player_{stat}_mean8']=[0.,2.,2.,4.]
    return frame


def baseline(q,category):
    frame=q[list(run.CONTEXT)].copy();support=category['support']
    frame['target']=category['target'];frame['method']='leaf_cdf'
    frame['mean']=[0.,2.5,4.5,6.5];frame['median']=[0.,2.,4.,6.]
    frame['point']=frame['median'];frame['probability']=np.nan
    if support=='bernoulli':frame['point']=frame['mean']=frame['median']=frame['probability']=[0.,.2,.8,1.]
    if support=='signed_integer':frame['median']=[-3.,0.,4.,10.];frame['point']=frame['median']
    frame['primary_role']=frame.position.isin(category['primary_roles'])
    frame['fallback']=['cold_prior','','',''];frame['history_state']=['cold_or_unknown','cold_or_unknown','warm','warm']
    frame['actual']=[0.,1.,0.,1.] if support=='bernoulli' else [-2.,0.,4.,8.] if support=='signed_integer' else [0.,2.,3.,7.]
    frame['participation_state']=['played','DNP','unknown','played']
    frame['outcome_state']=['played_zero' if frame['actual'].iloc[0]==0 else 'played_nonzero','DNP','unknown','played_nonzero']
    frame['qualified_outcome_state']=frame.outcome_state
    for name in run.shared.LAW_FIELDS:frame[name]=.123
    frame['year']=q.season
    return frame


class FakeStore:
    def report_retention(self):return {'charged_bytes':0,'limit_bytes':run.LIMIT}


class FakeSession:
    last=None
    def __init__(self,spec):
        FakeSession.last=self;self.spec=spec;self.output=Path(spec['output']);self.bindings={};self.frames={};self.docs={};self.storage=FakeStore()
    def write(self,name,value,**kwargs):self.docs[name]=copy.deepcopy(value);self.bindings[name]='a'*64
    def frame(self,name,value,**kwargs):self.frames[str(self.output/name)]=value.copy();self.bindings[name]='b'*64
    def failure(self,name,error):self.write(name,{'exception':type(error).__name__})
    def check(self):pass
    def usage(self,sequence):return dict(fits=sequence.fits,rows=sequence.rows)


class FakeModel:
    def __init__(self,category):self.category=category
    def predict(self,q,base):
        points=base.copy();valid=run.correction.baseline_support(base,self.category['support']);interior=run.correction.baseline_support(base,self.category['support'],fitting=True)
        apply=q.position.isin(self.category['primary_roles']).to_numpy()&interior
        points[apply]+=.05;points[~valid]=np.nan
        return points,np.where(apply,'','fictional_reference')
    def manifest(self):return {'fictional':True}


class OrchestrationChecks(unittest.TestCase):
    def test_sequence_forbids_early_labels_and_duplicate_fit(self):
        seq=run.Sequence(categories(),expected_rows=264)
        with self.assertRaises(ValueError):seq.before_labels(2022)
        with self.assertRaises(ValueError):seq.before_labels(2024,scoring=True)
        for slot in seq.planned[:22]:seq.reserve(slot,4);seq.freeze(slot,4)
        seq.before_labels(2022)
        slot=seq.planned[22];seq.reserve(slot,4);seq.consume_fit(slot)
        with self.assertRaises(ValueError):seq.consume_fit(slot)
        with self.assertRaises(ValueError):seq.before_labels(2023)

    def test_numeric_laws_cleared_and_baseline_fallback_preserved(self):
        for target in ('pass_att','pass_yd','anytime_td'):
            c=run.shared._category(categories(),target);q=query(2022);b=baseline(q,c)
            values=b['mean' if c['support']=='count' else 'median' if c['support']=='signed_integer' else 'probability'].to_numpy()
            rows=run.forecast_rows(q,b,values,c,run.correction.METHODS[0],startup=True)
            np.testing.assert_array_equal(rows.point,values)
            self.assertEqual(rows.baseline_fallback.tolist(),b.fallback.tolist())
            self.assertTrue(rows[['mean','median',*run.shared.LAW_FIELDS]].isna().all(axis=None))
            self.assertTrue(rows.fallback.eq('no_earlier_oof').all())

    def test_context_never_invents_legacy_optional_metadata(self):
        c=run.shared._category(categories(),'pass_att');q=query(2022);b=baseline(q,c)
        receipt=run.exact_context(q,b,c,2022)
        self.assertEqual(receipt['season_type'],'ABSENT_BOTH_FROZEN_LEGACY_PROJECTIONS')
        b['season_type']='REG'
        with self.assertRaises(ValueError):run.exact_context(q,b,c,2022)
        b=b.drop(columns='season_type');b.loc[0,'team']='OTHER'
        with self.assertRaises(AssertionError):run.exact_context(q,b,c,2022)

    def test_count_projection_uses_saved_mean_and_never_actual(self):
        c=run.shared._category(categories(),'pass_att');q=query(2022);b=baseline(q,c)
        spec={'control_metadata':{'2022':{'pass_att':{'leaf_cdf':dict(binding={'path':'fiction'},forecast_columns=list(run.CONTEXT)+list(run.BASE_FORECAST),label_columns=list(run.LABELS))}}}}
        def reader(path,columns):self.assertNotIn('actual',columns);return b[columns].copy()
        with patch.object(run.pd,'read_parquet',reader):_,point,receipt=run.baseline_projection(spec,q,c,2022)
        np.testing.assert_array_equal(point,b['mean']);self.assertFalse(receipt['labels_semantically_read'])

    def test_strict_seven_day_training_availability(self):
        c=run.shared._category(categories(),'pass_att');old=query(2022);current=query(2023)
        old['kickoff_utc']='2022-12-31T16:00:00Z';current['cutoff_utc']='2023-01-07T16:00:00Z'
        donor=baseline(old,c);seq=run.Sequence(categories())
        for slot in seq.planned[:22]:seq.reserve(slot,4);seq.freeze(slot,4)
        with patch.object(run,'baseline_projection',return_value=(donor,donor['mean'].to_numpy(),{})):
            frame,values,audit=run.training_frame({}, {2022:old,2023:current},c,2023,seq)
        self.assertEqual(len(frame),0);self.assertEqual(len(values),0);self.assertEqual(audit[0]['chronology_excluded_rows'],4)

    def test_per_fit_guard_rejects_identity_caps_and_elapsed_limits(self):
        marker=dict(active=True,pid=321,process_start_ticks=456,process_cpu_start=10.,cpu_clock='proc_utime_plus_stime_over_CLK_TCK',
            monotonic_start=20.,attempt=1,max_wall_seconds=20,max_CPU_seconds=20,generated_at='fiction')
        self.assertEqual(fit_guard(marker,pid=321,start_ticks=456,cpu_now=11.,monotonic_now=21.),(None,1))
        self.assertEqual(fit_guard(marker,pid=321,start_ticks=456,cpu_now=29.,monotonic_now=21.)[0],'PER_FIT_CPU_LIMIT')
        self.assertEqual(fit_guard(marker,pid=321,start_ticks=456,cpu_now=11.,monotonic_now=39.)[0],'PER_FIT_WALL_LIMIT')
        marker['max_CPU_seconds']=21
        self.assertEqual(fit_guard(marker,pid=321,start_ticks=456,cpu_now=11.,monotonic_now=21.)[0],'INVALID_FIT_GUARD_IDENTITY_OR_LIMITS')

    def test_full_mocked66_forecast44fit_two_failures_preserve_boundaries(self):
        cats=categories();queries={y:query(y) for y in run.shared.YEARS};tables={};spec=dict(registration_id=run.VERSION,
            output='/tmp/fictional-baseline-correction-not-written',queries={},query_metadata={},control_metadata={})
        for year,q in queries.items():
            path=f'fiction-query-{year}';tables[path]=q;spec['queries'][str(year)]={'path':path}
            spec['query_metadata'][str(year)]=dict(rows=4,projected_columns=list(q));spec['control_metadata'][str(year)]={}
            for target in cats:
                if target=='fantasy_ppr':continue
                c=run.shared._category(cats,target);b=baseline(q,c);path=f'fiction-control-{year}-{target}';tables[path]=b
                spec['control_metadata'][str(year)][target]={'leaf_cdf':dict(binding={'path':path},
                    forecast_columns=list(run.CONTEXT)+list(run.BASE_FORECAST),label_columns=[*run.LABELS,'qualified_outcome_state'])}
        sequences=[];actual_sequence=run.Sequence;fits=[];reads=[];reports=[]
        def sequence(cats):
            value=actual_sequence(cats,expected_rows=264);sequences.append(value);return value
        def reader(path,columns=None):
            path=str(path);seq=sequences[0]
            if path in tables:
                if path.startswith('fiction-control') and (columns is None or 'actual' in columns):
                    year=int(path.split('-')[2]);seq.before_labels(year,scoring=seq.global_frozen);reads.append((year,seq.global_frozen))
                result=tables[path]
            else:result=FakeSession.last.frames[path]
            return result.copy() if columns is None else result[columns].copy()
        def fit(train,base,category,method,*,query_year):
            self.assertTrue(train.season.lt(query_year).all());fits.append((query_year,category['target'],method))
            if query_year==2023 and category['target']=='pass_att' and method==run.correction.METHODS[0]:raise RuntimeError('fictional package fit failure')
            model=FakeModel(category)
            if query_year==2024 and category['target']=='rec_yd' and method==run.correction.METHODS[1]:
                model.predict=lambda *args:(_ for _ in ()).throw(RuntimeError('fictional prediction failure'))
            return model
        def control(session,year,target,method,category):
            self.assertTrue(sequences[0].global_frozen)
            value=tables[f'fiction-control-{year}-{target}'].copy();value['method']=method
            if method=='leaf_cdf' and category['support']=='count':value['point']=value['mean']
            return value
        def target_report(rows,controls,category,check):
            self.assertTrue(sequences[0].global_frozen);reports.append(category['target'])
            self.assertEqual(len(rows),24);self.assertEqual(len(controls),60)
            return dict(target=category['target'],fictional=True),pd.DataFrame({'fictional':[1]})
        with ExitStack() as stack:
            for owner,name,value in [(run,'Session',FakeSession),(run,'Sequence',sequence),
                (run,'metadata',lambda spec:({'category_contract':{'categories':cats},'control_scored_freeze':{}},{})),
                (run,'validate_owned_references',lambda *args:({},{})),(run,'process_free_threads',lambda *args:nullcontext()),
                (run,'threadpool_limits',lambda **args:nullcontext()),(run,'only_corrections',lambda:nullcontext()),
                (run,'_deadline',lambda *args:nullcontext()),(run.shared,'cpu_deadline',lambda *args:nullcontext()),
                (run.shared,'estimator_cpu_guard',lambda *args:nullcontext()),(run.pd,'read_parquet',reader),
                (run.correction.BaselineCorrection,'fit',fit),(run.parent,'_control',control),(run.parent,'target_report',target_report),
                (run.parent,'product_pairs',lambda *args,**kwargs:({'fictional':True},pd.DataFrame()))]:
                stack.enter_context(patch.object(owner,name,value))
            spec['loaded_libc']={};run.run(spec,plan_sha256=run.POLICY_SHA256,final_static=lambda:None)
        session=FakeSession.last;seq=sequences[0]
        self.assertEqual(len(fits),44);self.assertEqual(len(set(fits)),44);self.assertEqual(seq.rows,264)
        self.assertTrue(seq.global_frozen);self.assertEqual(len(reports),11)
        self.assertEqual(session.docs['CORRECTION_FINISHED.json']['state'],'COMPLETED')
        freeze=session.docs['forecast-freeze.json'];self.assertEqual(len(freeze['slots']),66)
        self.assertEqual(sum(s['state']=='STARTUP_ALIAS' for s in freeze['slots']),22)
        failed=[s for s in freeze['slots'] if s['state']=='FAILED_BASELINE_RETAINED'];self.assertEqual(len(failed),2)
        for slot in failed:
            rows=session.frames[str(session.output/slot['forecast'])]
            np.testing.assert_array_equal(rows.point,rows.baseline_point)
            self.assertTrue(rows.fallback.eq('package_failure_baseline_retained').all())
        self.assertIn((2023,False),reads);self.assertNotIn((2024,False),reads)
        self.assertEqual(session.docs['report.json']['scientific_qualification'],False)
        self.assertEqual(session.docs['report.json']['release_ready'],False)


if __name__=='__main__':unittest.main()
