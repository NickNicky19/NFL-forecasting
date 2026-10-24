"""Fictional metadata only; no forecast values, model loads or network."""
from copy import deepcopy
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from tools import export_weekly_public_feed_v1 as export


class CatalogAdmissionChecks(unittest.TestCase):
    def setUp(self):
        self.body=export.feed.canonical({'fictional':'metadata only'})+b'\n'
        self.ref={'path':'/fictional/original/catalog.json','bytes':len(self.body),'sha256':export.feed.sha(self.body)}
        self.plan={'selected_version_catalog':dict(self.ref,path='/fictional/fresh/catalog.json')}
        self.bundle={'terminal':{'selected_version_catalog':self.ref}}
        self.policy={'schema_version':export.feed.POLICY_V2}

    def test_authentic_relocated_catalog_is_checked_before_use(self):
        with patch.object(export,'read_ref',return_value=self.body),patch.object(export.feed,'catalog_policy_v2') as check:
            self.assertEqual(export.pre_value_catalog(self.plan,self.bundle,self.policy),{'version_catalog_body':self.body})
            check.assert_called_once()

    def test_changed_terminal_binding_rejects_before_recipe_or_value_admission(self):
        for field,value in [('bytes',len(self.body)+1),('sha256','f'*64)]:
            changed=deepcopy(self.bundle);changed['terminal']['selected_version_catalog'][field]=value
            with self.subTest(field=field),patch.object(export,'read_ref',return_value=self.body),\
                    patch.object(export.feed,'catalog_policy_v2') as check,self.assertRaises(export.feed.FeedError):
                try:export.pre_value_catalog(self.plan,changed,self.policy)
                finally:check.assert_not_called()

    def test_changed_serializer_rejects_before_recipe_or_value_admission(self):
        body=self.body[:-1];ref=dict(self.ref,bytes=len(body),sha256=export.feed.sha(body))
        with patch.object(export,'read_ref',return_value=body),patch.object(export.feed,'catalog_policy_v2') as check,\
                self.assertRaises(export.feed.FeedError):
            try:export.pre_value_catalog({'selected_version_catalog':ref},{'terminal':{'selected_version_catalog':ref}},self.policy)
            finally:check.assert_not_called()

    def test_v1_does_not_open_a_catalog(self):
        with patch.object(export,'read_ref') as read:
            self.assertEqual(export.pre_value_catalog({}, {}, {'schema_version':export.feed.POLICY}),{})
            read.assert_not_called()

    def test_live_acceptance_uses_existing_owner_and_refuses_overwrite(self):
        from nfl_lab.frozen_source_policy import load_frozen_source_policy
        from nfl_lab.operational_storage import OperationalStorage
        from nfl_lab.owned_reference_batch import validate_owned_references
        source_path=Path(__file__).resolve().parents[1]/'config/operational-source-policy-v2.json'
        raw=source_path.read_bytes();source=load_frozen_source_policy(source_path)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);cache=root/'cache';state=root/'state';destination=root/'receipt.json'
            store=OperationalStorage(cache,source,state=state);store.register_root(root)
            plan=dict(source_policy={'path':str(source_path),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()},
                cache_root=str(cache),state_root=str(state),durability_acceptance_output=str(destination))
            export.persist_live_acceptance(plan,{'source_policy_sha256':source['_policy_sha256']},{'fictional':'API receipt'})
            validate_owned_references(store,{str(destination):hashlib.sha256(destination.read_bytes()).hexdigest()})
            with self.assertRaises(export.feed.FeedError):
                export.persist_live_acceptance(plan,{'source_policy_sha256':source['_policy_sha256']},{'fictional':'API receipt'})


if __name__=='__main__':unittest.main()
