"""Fictional clocks/IDs/transports only; no NFL, fitting or model decoding."""
from copy import deepcopy
from contextlib import contextmanager
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from nfl_lab import weekly_generic_producer as g, weekly_adaptive as selector
from nfl_lab.state import digest,utc

ROOT=Path(__file__).resolve().parents[1]
NOW=utc("2026-10-27T09:00:00Z")


def plan():
    years=list(range(2019,2027))
    return dict(schema_version=g.VERSION,state="FROZEN_ROOT_REVIEWER_SEALED",execution_authorized=True,
        code_pins={"nfl_lab/weekly_generic_producer.py":"a"*64,"nfl_lab/weekly_adaptive.py":"b"*64},
        review=dict(status="PREEXEC_PASS",integrator="/root"),budgets=dict(g.LIMITS),HTTP=0,source_mode="ADOPT_VERIFIED_CACHE",
        model_boundary=g.MODEL_BOUNDARY,export_boundary=g.EXPORT_BOUNDARY,retention_physical_anchor=0,
        history_seasons=years,allowed_periods={str(y):list(range(1,8 if y==2026 else 19)) for y in years},
        slate=g.prepare_slate([dict(season=2026,week=8,game_type="REG",game_id="fictional-game",kickoff_utc="2026-10-29T20:00:00Z")],
            season=2026,week=8,game_cutoffs={"fictional-game":"2026-10-29T19:00:00Z"},now=NOW))


def selection_fixture():
    policy=dict(categories=[dict(category="pass_att",startup_method_id="LAB_CDF"),dict(category="anytime_td",startup_method_id="TD_EQUAL_CDF_CAT"),
        dict(category="fantasy_ppr",startup_method_id="R0_UNCHANGED")],TD_EQUAL_CDF_CAT={"members":{"LAB_CDF":.5,"CATBOOST_MEDIUM":.5}})
    methods={m:dict(model_versions=[m+"-model"],procedure_version=m+"-procedure",registered_at="2026-10-20T00:00:00Z",
        procedure_operational_eligible=m!="R0") for m in ("LAB_CDF","CATBOOST_MEDIUM","R0")}
    categories={t:dict(state="READY",support=s,product=p,primary_metric=metric,reference_id="R0",shortlist=["LAB_CDF","CATBOOST_MEDIUM"],
        eligible_methods=["R0","LAB_CDF","CATBOOST_MEDIUM"]) for t,s,p,metric in [("pass_att","count","point_mean","point_mse"),("anytime_td","bernoulli","binary_probability","brier")]}
    catalog=dict(schema_version=selector.VERSION,methods=methods,categories=categories)
    history=dict(schema_version=selector.VERSION,offers=[],forecasts=[],outcomes=[],decisions=[],weeks=[])
    return policy,catalog,history


class GenericProducerChecks(unittest.TestCase):
    def test_builder_metadata_stays_charged_and_only_remaining_capacity_is_admitted(self):
        from nfl_lab.operational_storage import OperationalStorage, StorageQuotaError
        from tools.weekly_current_query import study_storage_class
        policy=json.loads((ROOT/'config/operational-source-policy-v2.json').read_text())
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            original=OperationalStorage(root/'cache',policy,state=root/'state');original.register_root(root)
            anchor=original.snapshot()['physical_bytes']
            original.atomic_json(root/'CATALOG.json',{'fixture':'fictional metadata remains charged'})
            original.atomic_json(root/'PLAN.json',{'fixture':'fictional plan remains charged'})
            guarded=study_storage_class(OperationalStorage)(root/'cache',policy,state=root/'state',
                study_anchor=anchor,study_bytes=g.LIMITS['new_bytes'])
            used=guarded.snapshot()['physical_bytes']-anchor
            self.assertGreater(used,0)
            with self.assertRaises(RuntimeError):guarded._require(g.LIMITS['new_bytes'])
            remaining=g.admit_remaining_output(guarded,anchor)
            self.assertEqual(remaining,g.LIMITS['new_bytes']-used)
            self.assertEqual(guarded.study_anchor,anchor)
            with self.assertRaises(RuntimeError):guarded._require(remaining+1)
            self.assertTrue((root/'CATALOG.json').is_file())
            self.assertTrue((root/'PLAN.json').is_file())
            with self.assertRaises(ValueError):g.admit_remaining_output(guarded,guarded.snapshot()['physical_bytes']+1)
        limited=deepcopy(policy);limited['storage']['limit_bytes']=8192
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);store=OperationalStorage(root/'cache',limited,state=root/'state');store.register_root(root)
            anchor=store.snapshot()['physical_bytes']
            store.atomic_json(root/'PLAN.json',{'fixture':'not enough global quota for full remaining study'})
            guarded=study_storage_class(OperationalStorage)(root/'cache',limited,state=root/'state',
                study_anchor=anchor,study_bytes=g.LIMITS['new_bytes'])
            with self.assertRaises(StorageQuotaError):g.admit_remaining_output(guarded,anchor)

    def test_production_orchestration_calls_real_boundaries_with_fictional_transports(self):
        """Run the production control flow, replacing only source/store/models."""
        import pandas as pd
        from nfl_lab import weekly_future_inference as future, weekly_current_inference as current
        from nfl_lab import operational_sources as source, weekly_current_query as query
        starts=dict(training_source_capture_completed_at="2026-08-01T00:00:00Z",training_started_at="2026-08-02T00:00:00Z",training_completed_at="2026-08-03T00:00:00Z")
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory);p=plan();p.update(cache=str(base/'cache'),state_root=str(base/'state'),output_root=str(base/'output'),
                source_cache=str(base/'source'),source_contract={'source_policy_sha256':'f'*64,
                    'availability_rule':'FROZEN_KICKOFF_PLUS_7DAY_RECONSTRUCTION','feature_builder_sha256':'e'*64},
                source_freshness_seconds=dict(schedule=86400,current_roster=86400,current_statistics=86400,players=604800),
                history_bundle=None,previous_choices=None,frozen_weekly_choice=None,reference_forecasts=None)
            raw=base/'source/raw';raw.mkdir(parents=True)
            def save(name,doc):
                path=base/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(doc));return future.binding(path)
            p['source_bindings']=[]
            for name in source._names(p['history_seasons']):
                (raw/name).write_bytes(b'fictional source body')
                (raw/(name+'.receipt.json')).write_text(json.dumps(dict(status='acquired',retrieved_utc='2026-10-27T08:00:00Z')))
            pd.DataFrame([dict(season=2026,week=8,game_type='REG',game_id='fictional-game',gameday='2026-10-29',gametime='16:00',home_team='A',away_team='B',espn='100001')]).to_csv(raw/'schedules.csv',index=False)
            pd.DataFrame([dict(season=2026,week=8,game_type='REG',team=t,gsis_id=i,position=role,status='ACT',full_name='Fictional',sleeper_id=s)
                for t,i,role,s in [('A','00-0000001','QB','1234'),('B','00-0000002','RB','2345')]]).to_parquet(raw/'roster_weekly_2026.parquet',index=False)
            p['source_bindings']=[future.binding(x) for x in raw.iterdir()];p['schedule']=future.binding(raw/'schedules.csv');p['roster']=future.binding(raw/'roster_weekly_2026.parquet')
            startup={**{t:'LAB_CDF' for t in ('pass_yd','pass_td','pass_cmp','pass_att','pass_int','rush_yd')},'rush_att':'COUNT_A','rec':'COUNT_A','rec_yd':'CATBOOST_MEDIUM','rush_rec_yd':'CATBOOST_MEDIUM','anytime_td':'TD_EQUAL_CDF_CAT'}
            policy=dict(schema_version='weekly-provisional-live-policy-v1',categories=[dict(category=t,startup_method_id=m) for t,m in startup.items()],TD_EQUAL_CDF_CAT={'members':{'LAB_CDF':.5,'CATBOOST_MEDIUM':.5}})
            catalog=dict(schema_version=selector.VERSION,methods={},categories={});p['artifacts']=[];manifests={}
            for target,method in sorted(current.EXPECTED):
                support='bernoulli' if target=='anytime_td' else 'signed_integer' if target.endswith('_yd') else 'count'
                product,functional,metric=future.product({'support':support})
                category=dict(target=target,support=support,primary_roles=['QB'] if target.startswith('pass_') else ['RB'],modeled_roles=['QB','RB'])
                m=dict(category=category,method_id=method,family={'LAB_CDF':'leaf_cdf_base','CATBOOST_MEDIUM':'catboost_medium','COUNT_A':'count_A'}[method],
                    source_contract=p['source_contract'],procedure_version=method+'-procedure',training_cutoff_utc='2026-09-01T00:00:00Z',features=['f_fixture','f_player_games_prior'],product=product,fit_receipt=starts)
                ref=save(f'models/{target}-{method}.json',m);p['artifacts'].append(ref);manifests[ref['sha256']]=m
                spec=catalog['methods'].setdefault(method,dict(procedure_version=m['procedure_version'],model_versions=[],registered_at='2026-10-20T00:00:00Z',procedure_operational_eligible=True));spec['model_versions'].append(ref['sha256'])
                c=catalog['categories'].setdefault(target,dict(state='READY',support=support,product=product,primary_metric={'MSE':'point_mse','MAE':'point_mae','Brier':'brier'}[metric],reference_id='R0',shortlist=[],eligible_methods=['R0']))
                c['shortlist'].append(method);c['eligible_methods'].append(method)
            catalog['methods']['R0']=dict(procedure_version='UNAVAILABLE_NO_R0',model_versions=[],registered_at='2026-10-20T00:00:00Z',procedure_operational_eligible=False)
            p['selector_catalog']=save('catalog.json',catalog);p['startup_policy']=save('policy.json',policy)
            p['owned_inputs']=[*p['artifacts'],*p['source_bindings'],p['selector_catalog'],p['startup_policy']]
            class Store:
                @contextmanager
                def transaction(self):yield
                def _require(self,n):return {'physical_bytes':0}
                def register_root(self,path):Path(path).mkdir();return Path(path)
                def write_bytes(self,path,body):Path(path).parent.mkdir(parents=True,exist_ok=True);Path(path).write_bytes(body)
                def write_dataframe(self,frame,path,**kw):Path(path).parent.mkdir(parents=True,exist_ok=True);frame.to_parquet(path,**kw)
            @contextmanager
            def operation(*args,**kwargs):yield {'fictional_only':True}
            @contextmanager
            def fictional_feature_owner(owner,sink):
                # This orchestration fixture injects a fake store; real ownership
                # and unchanged sink reserve are covered by the actual-owner test.
                yield owner
            request={'fictional':'request'};request_path=base/'cache/operational-source-v2'/('f'*64)/'requests'/(source._digest(request)+'.json');request_path.parent.mkdir(parents=True);request_path.write_text('{}')
            manifest=dict(request=request,namespace=str(base/'namespace'),manifest_sha256='c'*64,source_receipts={x.name[:-13]:json.loads(x.read_text()) for x in raw.glob('*.receipt.json')})
            def shared(prior,packet,**kw):return packet['queries'].assign(f_fixture=1.,f_player_games_prior=1.,feature_max_source_available_utc=NOW-pd.Timedelta(hours=1))
            class Session:
                def prepare(self,refs):pass
                def _verify(self,refs):pass
                def close(self):pass
                def predict_chunks(self,version,frame,*,context,clock,batch_size):
                    m=manifests[version];out=[];product,functional,metric=future.product(m['category'])
                    for r in frame.to_dict('records'):
                        identity={k:r[k] for k in ('season','week','game_id','player_id')};identity['category']=m['category']['target']
                        out.append(dict(identity,offered_id=digest(identity),slate_id=context['slate_id'],horizon='player_game',team=r['team'],opponent=r['opponent'],position=r['position'],
                            kickoff_utc=utc(r['kickoff_utc']).isoformat(),cutoff_utc=utc(r['cutoff_utc']).isoformat(),issued_at=clock().isoformat(),
                            method_id=m['method_id'],model_version=version,artifact_sha256=version,procedure_version=m['procedure_version'],
                            product=product,prediction_functional=functional,metric=metric,forecast_value=.2 if metric=='Brier' else -2.5 if metric=='MAE' else 2.5,
                            fallback_reason='',operational_eligible=True,evidence_lane='original_pregame',reference_stream='candidate',
                            training_cutoff_utc=m['training_cutoff_utc'],training_max_available_utc='2026-01-01T00:00:00Z',**starts,
                            source_capture_completed_at=NOW.isoformat(),source_policy_sha256='f'*64))
                    yield out
            backend=object.__new__(g.ProductionBackend);backend.plan=p;backend.store=Store();backend.policy={'_policy_sha256':'f'*64};backend.clock=lambda:NOW;backend.resource_check=lambda:None
            with patch('nfl_lab.owned_reference_batch.validate_owned_references'),patch.object(g,'owned_feature_output',fictional_feature_owner),patch('nfl_lab.weekly_source_read_batch.source_read_operation',operation),patch('nfl_lab.weekly_source_read_batch.manifest_bindings',return_value={}),\
                patch.object(source,'acquire_operational_history',return_value=manifest) as acquire,patch.object(source,'load_operational_history',return_value=pd.DataFrame()),\
                patch.object(query,'build_shared_features',side_effect=shared),patch.object(future.FutureInferenceSession,'from_storage',return_value=Session()):
                result=backend.run()
            self.assertIsNone(result['fatal'],result['fatal']);self.assertEqual(result['state'],'LOCAL_FUTURE_SLATE_CAPTURED')
            self.assertEqual(result['selected']['rows'],11);self.assertEqual(acquire.call_count,1)
            self.assertEqual(result['candidate_capture']['prediction_rows'],36)
            self.assertFalse(result['public_export_authorized']);self.assertEqual(result['HTTP'],0)

    def test_prepare_derives_actual_full_week_deadline_and_keeps_elapsed(self):
        rows=[dict(season=2026,week=8,game_type="REG",game_id="early",kickoff_utc="2026-10-26T20:00:00Z"),
            dict(season=2026,week=8,game_type="REG",game_id="later",kickoff_utc="2026-10-29T20:00:00Z")]
        s=g.prepare_slate(rows,season=2026,week=8,game_cutoffs={"later":"2026-10-29T19:00:00Z"},now=NOW)
        self.assertEqual(s["weekly_deadline_utc"],"2026-10-26T14:00:00+00:00")
        self.assertEqual((s["scheduled_games"],s["elapsed_games"]),(2,1))
        with self.assertRaisesRegex(ValueError,"coverage cut"):
            g.prepare_slate(rows,season=2026,week=8,game_cutoffs={},now=NOW)

    def test_plan_no_backdate_no_refresh_no_new_season_or_budget(self):
        p=plan();g.validate_plan(p,now=NOW)
        for field,value in [("execution_authorized",False),("HTTP",1),("source_mode","HTTP"),("retention_physical_anchor",None)]:
            q=deepcopy(p);q[field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):g.validate_plan(q,now=NOW)
        q=deepcopy(p);q["slate"]["game_cutoffs"]["fictional-game"]="2026-10-27T08:00:00Z"
        with self.assertRaisesRegex(ValueError,"backdated"):g.validate_plan(q,now=NOW)
        q=deepcopy(p);q["history_seasons"]=q["history_seasons"][-1:]
        with self.assertRaisesRegex(ValueError,"earlier supported"):g.validate_plan(q,now=NOW)

    def test_january_keeps_preceding_nfl_season_not_calendar_year(self):
        p=plan();p["slate"]["week"]=18;p["slate"]["game_cutoffs"]={"fictional":"2027-01-04T18:00:00Z"}
        p["slate"]["weekly_deadline_utc"]="2027-01-04T12:00:00Z"
        g.validate_plan(p,now=utc("2027-01-01T00:00:00Z"))
        p["slate"]["season"]=2027
        with self.assertRaisesRegex(ValueError,"active season"):g.validate_plan(p,now=utc("2027-01-01T00:00:00Z"))

    def test_stale_cache_and_forged_future_retrieval_fail_closed(self):
        limits=dict(schedule=86400,current_roster=86400,current_statistics=86400,players=604800)
        refs={n:dict(status="acquired",retrieved_utc="2026-10-27T08:00:00Z") for n in
            ("schedules.csv","roster_weekly_2026.parquet","stats_player_week_2026.parquet","players.parquet")}
        g.validate_freshness(refs,now=NOW,season=2026,limits=limits)
        for field,value in [("status","stale_cache"),("retrieved_utc","2026-10-24T00:00:00Z"),("retrieved_utc","2026-10-28T00:00:00Z")]:
            q=deepcopy(refs);q["schedules.csv"][field]=value
            with self.subTest(value=value),self.assertRaisesRegex(ValueError,"stale/future"):g.validate_freshness(q,now=NOW,season=2026,limits=limits)

    def test_choice_is_prior_only_and_startup_TD_keeps_real_components(self):
        policy,catalog,history=selection_fixture();s=plan()["slate"]
        chosen=g.freeze_choices(selector,history,catalog,policy,s,actual_choice_at=NOW)
        td=next(r for r in chosen["selections"] if r["decision"]["category"]=="anytime_td")
        self.assertEqual([(r["method_id"],r["weight"]) for r in td["members"]],[("LAB_CDF",.5),("CATBOOST_MEDIUM",.5)])
        self.assertTrue(all("training_started_at" not in r for r in td["members"]))
        self.assertEqual(chosen["actual_frozen_at"],NOW.isoformat())
        self.assertNotEqual(chosen["actual_frozen_at"],s["weekly_deadline_utc"])
        with self.assertRaisesRegex(ValueError,"deadline"):
            g.freeze_choices(selector,history,catalog,policy,s,actual_choice_at=utc(s["weekly_deadline_utc"]))

    def test_restore_rejects_changed_procedure_and_slate(self):
        policy,catalog,history=selection_fixture();s=plan()["slate"]
        frozen=g.freeze_choices(selector,history,catalog,policy,s,actual_choice_at=NOW)
        self.assertEqual(g.restore_choices(frozen,slate=s,catalog=catalog,policy=policy,selector=selector,now=NOW),frozen)
        q=deepcopy(catalog);q["methods"]["LAB_CDF"]["procedure_version"]="changed"
        with self.assertRaisesRegex(ValueError,"procedure/catalog"):g.restore_choices(frozen,slate=s,catalog=q,policy=policy,selector=selector,now=NOW)
        q=deepcopy(s);q["schedule_identity_sha256"]="changed"
        with self.assertRaisesRegex(ValueError,"prior weekly freeze"):g.restore_choices(frozen,slate=q,catalog=catalog,policy=policy,selector=selector,now=NOW)

    def test_selected_wrapper_versions_are_metadata_bound_before_values(self):
        policy,catalog,history=selection_fixture();s=plan()["slate"]
        frozen=g.freeze_choices(selector,history,catalog,policy,s,actual_choice_at=NOW)
        records=[dict(binding={"sha256":m+"-model"},manifest={"category":{"target":t},"method_id":m})
            for t in ("pass_att","anytime_td") for m in ("LAB_CDF","CATBOOST_MEDIUM")]
        codes=plan()["code_pins"];registered=g.register_selected_versions(frozen,records,catalog,codes)
        self.assertFalse(registered["current_values_used"])
        self.assertTrue(any(r["category"]=="anytime_td" for r in registered["rows"]))
        changed=dict(codes);changed["nfl_lab/weekly_generic_producer.py"]="c"*64
        self.assertNotEqual(g.selected_procedure(frozen["selections"][0],codes),g.selected_procedure(frozen["selections"][0],changed))

    def test_arbitrary_injected_production_backend_cannot_run(self):
        class Fictional:
            fictional_only=True
            def run(self):return {"state":"FICTIONAL_ONLY"}
        with self.assertRaisesRegex(ValueError,"real APIs"):g.execute(plan(),backend=Fictional(),clock=lambda:NOW)
        p=plan();p["fictional_only"]=True
        self.assertEqual(g.execute(p,backend=Fictional(),clock=lambda:NOW)["state"],"FICTIONAL_ONLY")

    def test_exact_bridge_rejects_namespace_and_kickoff_mismatch(self):
        import pandas as pd
        schedule=pd.DataFrame([dict(season=2026,week=8,game_type="REG",game_id="fictional",gameday="2026-10-29",gametime="16:00",home_team="A",away_team="B",espn="100001")])
        queries=pd.DataFrame([dict(season=2026,week=8,game_id="fictional",player_id="00-0000001",sleeper_id="1234",team="A",opponent="B",kickoff_utc="2026-10-29T20:00:00Z")])
        kwargs=dict(schedule_binding={"sha256":"a"*64},query_binding={"sha256":"b"*64},season=2026,week=8)
        row=next(iter(g.exact_bridge(queries,schedule,**kwargs).values()))
        self.assertEqual(row["website_player_id"],"1234");self.assertEqual(row["website_game_id"],"100001")
        self.assertEqual(row["identity_binding_sha256"],digest({k:v for k,v in row.items() if k!="identity_binding_sha256"}))
        queries.loc[0,"kickoff_utc"]="2026-10-29T21:00:00Z"
        with self.assertRaisesRegex(ValueError,"kickoff bridge"):g.exact_bridge(queries,schedule,**kwargs)

    def test_unsealed_CLI_refuses_before_resource_changes_or_imports(self):
        spec=importlib.util.spec_from_file_location("fictional_generic_cli",ROOT/"tools/weekly_generic_future_producer.py")
        cli=importlib.util.module_from_spec(spec);spec.loader.exec_module(cli)
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/"prep.json";p.write_text(json.dumps(dict(state="PREPARED",execution_authorized=False)))
            import hashlib
            with patch("sys.argv",["cli","--plan",str(p),"--plan-sha256",hashlib.sha256(p.read_bytes()).hexdigest(),"--execute"]),patch.object(cli.resource,"setrlimit",side_effect=AssertionError("resource mutation before seal")):
                with self.assertRaisesRegex(ValueError,"not source/model/runtime authority"):cli.main()


if __name__=="__main__":unittest.main()
