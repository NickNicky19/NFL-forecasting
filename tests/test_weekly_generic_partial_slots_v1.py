"""Fictional metadata/forecasts only; no real models, targets or transport."""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
import unittest

import pandas as pd

from nfl_lab import weekly_generic_producer as g,weekly_adaptive as selector
from nfl_lab import weekly_initial_remaining_v1 as initial
from nfl_lab.hosted_fixed_build_v1 import jobs
from nfl_lab.state import digest,utc

ROOT=Path(__file__).resolve().parents[1]
NOW=utc('2026-10-24T12:00:00Z')
FIT=dict(training_source_capture_completed_at='2026-10-24T11:56:00Z',training_started_at='2026-10-24T11:57:00Z',training_completed_at='2026-10-24T11:58:00Z')


def fixture(failed=(),not_ready=(),relocated=False):
    document=json.loads((ROOT/'reports/all12-leaf-cdf-v1/method-config.json').read_text())
    categories={t:dict(c,target=t) for t,c in document['categories'].items() if c['state']=='READY'}
    contract=dict(source_policy_sha256='e7f54213218031c978c766af7a1a3b22a57c2a424b51f62056742162154fe441',
        feature_builder_sha256='0c79adea3eb0feb9c5f634f48e546578ed3632e4d20dfdd05dc323c523dafc3c',availability_rule='FROZEN_KICKOFF_PLUS_7DAY_RECONSTRUCTION')
    def ref(name):return dict(path='fictional/'+name,bytes=100,sha256=digest(name))
    category_ref=dict(path='fictional/category.json',bytes=100,sha256=g.CATEGORY_SHA256)
    terminal_ref=ref('BUILD.json');inventory_ref=ref('slots.json');catalog_ref=ref('catalog.json')
    terminal=dict(schema_version='GENUINE_HOSTED_FIXED_BUILD_V1',state='BUILD_PARTIAL_OR_FAILED_RETAINED',source={'source_contract':contract},
        new_operational_model_build=True,old_model_reproduction=False,scoring=0,searches=0,training={'slots':[]})
    inventory=dict(schema_version=g.SLOT_INVENTORY,build_terminal=terminal_ref,category_contract=category_ref,
        selector_catalog_sha256=catalog_ref['sha256'],source_contract=contract,slots=[])
    catalog=dict(categories={t:dict(support=c['support'],shortlist=[]) for t,c in categories.items()})
    docs={category_ref['path']:document,terminal_ref['path']:terminal,inventory_ref['path']:inventory}
    plan=dict(slot_inventory=inventory_ref,source_contract=contract,selector_catalog=catalog_ref,owned_inputs=[terminal_ref,inventory_ref],artifacts=[])
    for job in jobs():
        key=(job['target'],job['method_id']);catalog['categories'][job['target']]['shortlist'].append(job['method_id'])
        slot=dict(job,availability='UNAVAILABLE' if key in failed or key in not_ready else 'READY',artifact=None,original_artifact=None,unavailable_reason=None)
        prior=dict(job,state='FAILED_FIT_RETAINED_NO_RETRY' if key in failed else 'NEW_OPERATIONAL_ARTIFACT_EXPORTED')
        if key in failed:slot['unavailable_reason']=prior['state']
        else:
            original=ref(job['target']+'-'+job['method_id']+'.json');prior.update(artifact=dict(original,path='/original/'+Path(original['path']).name),fit_receipt=dict(FIT))
            m=dict(category=categories[job['target']],method_id=job['method_id'],family=job['family'],source_contract=contract,
                fit_receipt=dict(FIT),artifact_created_at='2026-10-24T11:59:00Z',model=ref(job['target']+'-'+job['method_id']+'.joblib'))
            docs[original['path']]=m;plan['owned_inputs'].append(original);slot['original_artifact']=original
            if key in not_ready:slot['unavailable_reason']='MODEL_NOT_READY'
            else:
                slot['artifact']=original
                if relocated:
                    target=ref('relocated-'+job['target']+'-'+job['method_id']+'.json');new_model=dict(m['model'],path='/restored/'+Path(m['model']['path']).name)
                    docs[target['path']]=dict(m,model=new_model,relocation=dict(schema_version=g.MODEL_BOUNDARY,original_manifest=original,
                        original_model=m['model'],relocated_model_path=new_model['path'],parameters_fixtures_code_source_unchanged=True,model_decodes=0))
                    slot['artifact']=target;plan['owned_inputs'].append(target)
                plan['artifacts'].append(slot['artifact'])
        inventory['slots'].append(slot);terminal['training']['slots'].append(prior)
    return plan,catalog,docs,lambda ref,**kwargs:deepcopy(docs[ref['path']])


def resolve(value):
    plan,catalog,docs,_=value
    return g.read_slot_inventory(plan,catalog,lambda ref,**kwargs:deepcopy(docs[ref['path']]))


class PartialSlotChecks(unittest.TestCase):
    def test_success_and_failed_slots_bound_to_original_build_not_caller_subset(self):
        value=fixture(failed={('rec','COUNT_A')});result=resolve(value)
        self.assertEqual(len(result['original_metadata']),17);self.assertEqual(len(result['unavailable']),1)
        self.assertEqual(result['unavailable'][0]['reason'],'FAILED_FIT_RETAINED_NO_RETRY')
        plan,catalog,docs,_=value;docs[plan['slot_inventory']['path']]['slots'].pop()
        with self.assertRaisesRegex(ValueError,'eighteen-slot'):resolve(value)

    def test_inventory_extra_duplicate_catalog_and_policy_changes_fail(self):
        for kind in ('extra','duplicate','catalog','policy'):
            value=fixture();plan,catalog,docs,_=value;inventory=docs[plan['slot_inventory']['path']]
            if kind=='extra':inventory['extra']=True
            elif kind=='duplicate':inventory['slots'][-1]=deepcopy(inventory['slots'][0])
            elif kind=='catalog':inventory['selector_catalog_sha256']='0'*64
            else:inventory['source_contract']=dict(inventory['source_contract'],source_policy_sha256='0'*64)
            with self.subTest(kind=kind),self.assertRaises(ValueError):resolve(value)

    def test_failed_slot_cannot_be_promoted_or_omitted_from_artifact_inventory(self):
        value=fixture(failed={('rec','COUNT_A')});plan,_,docs,_=value;inventory=docs[plan['slot_inventory']['path']]
        inventory['slots'][12]['availability']='READY'
        with self.assertRaises(ValueError):resolve(value)
        value=fixture();value[0]['artifacts'].pop()
        with self.assertRaisesRegex(ValueError,'artifact list'):resolve(value)

    def test_success_hash_fit_clock_and_category_are_exact_original_bindings(self):
        for field in ('sha256','fit_receipt','category'):
            value=fixture();plan,_,docs,_=value;slot=docs[plan['slot_inventory']['path']]['slots'][0]
            if field=='sha256':slot['original_artifact']['sha256']='0'*64
            elif field=='fit_receipt':docs[slot['original_artifact']['path']][field]['training_started_at']='2026-10-24T10:00:00Z'
            else:docs[slot['original_artifact']['path']][field]['primary_roles']=['FB']
            with self.subTest(field=field),self.assertRaises(ValueError):resolve(value)

    def test_exact_relocation_preserves_model_bytes_source_and_original_manifest(self):
        value=fixture(relocated=True);self.assertEqual(len(resolve(value)['original_metadata']),18)
        plan,_,docs,_=value;m=docs[plan['artifacts'][0]['path']];m['model']['sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'relocation'):resolve(value)

    def test_all_unavailable_still_offer_all11_categories_and_all_unknown_identities(self):
        failed={(r['target'],r['method_id']) for r in jobs()};slots=resolve(fixture(failed=failed))
        queries=pd.DataFrame([dict(season=2026,week=7,game_id='fictional-game',player_id=role,position=role,team='A',opponent='B',
            kickoff_utc='2026-10-25T13:30:00Z',cutoff_utc='2026-10-24T15:00:00Z',participation_state='unknown') for role in ('QB','RB','FB','WR','TE')])
        records=[dict(manifest={'category':c}) for c in slots['categories'].values()]
        offers=g.offers(queries,records,{'slate_id':'fictional'})
        self.assertEqual({r['category'] for r in offers},set(slots['categories']));self.assertEqual(len(offers),len({r['offered_id'] for r in offers}))
        statuses=g.unavailable_capture(slots,queries)
        self.assertEqual(len(statuses),18);self.assertTrue(all(s['issued_rows']==0 and s['persistence'] is None for s in statuses))
        self.assertEqual(sum(s['expected_rows'] for s in statuses),sum(len(s['unissued_offered_ids']) for s in statuses))

    def test_model_not_ready_keeps_original_success_and_checks_all_actual_fit_clocks(self):
        slots=resolve(fixture(not_ready={('anytime_td','CATBOOST_MEDIUM')}))
        registration={'registered_at_utc':'2026-10-24T11:54:37Z'}
        receipts={n:dict(status='acquired',retrieved_utc='2026-10-24T11:55:00Z') for n in
            ('schedules.csv.receipt.json','roster_weekly_2026.parquet.receipt.json','stats_player_week_2026.parquet.receipt.json')}
        initial.validate_fresh_initial_metadata(registration,slots['original_metadata'],receipts,now=NOW,slot_inventory=slots)
        slots['original_metadata'][0]['fit_receipt']['training_source_capture_completed_at']='2026-10-24T10:00:00Z'
        with self.assertRaisesRegex(ValueError,'clocks'):initial.validate_fresh_initial_metadata(registration,slots['original_metadata'],receipts,now=NOW,slot_inventory=slots)
        with self.assertRaisesRegex(ValueError,'eighteen-model'):initial.validate_fresh_initial_metadata(registration,[],receipts,now=NOW)

    def test_incomplete_TD_has_whole_reference_or_abstains_without_renormalization(self):
        members=[dict(method_id=m,procedure_version=m,choice_eligible=True,weight=.5) for m in ('LAB_CDF','CATBOOST_MEDIUM')]
        selection=dict(members=members,decision={'category':'anytime_td'})
        class Panel:
            categories={'anytime_td':{'reference_id':'R0'}}
            def eligible(self,method,offer,lane):return method in {'LAB_CDF','R0'}
        class FakeSelector:
            @staticmethod
            def issue(panel,selected):
                methods=[m['method_id'] if panel.eligible(m['method_id'],{},'original_pregame') else 'R0' for m in selected['members']]
                return [dict(components=[dict(method_id=m,weight=.5) for m in methods],fallback_reason='')]
        original=deepcopy(selection);rows=g.issue_registered(FakeSelector,Panel(),selection,atomic_TD=True)
        self.assertEqual([(m['method_id'],m['weight']) for m in rows[0]['components']],[('R0',.5),('R0',.5)])
        self.assertEqual(selection,original)
        rows=g.issue_registered(FakeSelector,Panel(),selection,atomic_TD=False)
        self.assertEqual(rows[0]['components'][0]['method_id'],'LAB_CDF')

    def test_real_issue_keeps_each_offer_and_frozen_choice_with_missing_R0(self):
        methods={m:dict(procedure_version=m) for m in ('LAB_CDF','CATBOOST_MEDIUM','R0')}
        categories={'anytime_td':dict(reference_id='R0',product='binary_probability',primary_metric='brier')}
        catalog=dict(schema_version=selector.VERSION,methods=methods,categories=categories)
        decision=dict(category='anytime_td',season=2026,week=7,slate_id='fictional',horizon='player_game',evidence_lane='original_pregame',
            weekly_decision_cutoff_utc=NOW.isoformat(),slate_first_kickoff_utc='2026-10-25T13:30:00Z')
        offer=dict(decision,offered_id='fictional-offer',game_id='fictional-game',player_id='fictional-player',
            kickoff_utc='2026-10-25T13:30:00Z',cutoff_utc='2026-10-24T15:00:00Z')
        selection=dict(decision=decision,implementation_revision=selector.IMPLEMENTATION_REVISION,catalog_sha256=digest(selector.procedure_catalog(catalog)),policy='P2',
            members=[dict(method_id=m,procedure_version=m,choice_eligible=True,weight=.5) for m in ('LAB_CDF','CATBOOST_MEDIUM')])
        forecasts={('fictional-offer',m):dict(model_version=m,value=.9 if m=='LAB_CDF' else .2,forecast_value=.9 if m=='LAB_CDF' else .2,
            prediction_functional='probability') for m in ('LAB_CDF','R0')}
        panel=SimpleNamespace(catalog=catalog,methods=methods,categories=categories,decision_contracts={},offers_for=lambda key:[offer],
            forecasts=forecasts,eligible=lambda method,offer,lane:method in {'LAB_CDF','R0'},procedure_available=lambda method,decision:True)
        rows=g.issue_registered(selector,panel,selection,atomic_TD=True)
        self.assertEqual(len(rows),1);self.assertEqual(rows[0]['forecast_value'],.2)
        self.assertEqual([c['weight'] for c in rows[0]['components']],[.5,.5]);self.assertEqual(rows[0]['selection_sha256'],digest(selection))
        panel.eligible=lambda method,offer,lane:method=='LAB_CDF';panel.procedure_available=lambda method,decision:method!='R0'
        rows=g.issue_registered(selector,panel,selection,atomic_TD=True)
        self.assertEqual(len(rows),1);self.assertEqual(rows[0]['state'],'ABSTAIN');self.assertIsNone(rows[0]['forecast_value'])


if __name__=='__main__':unittest.main()
